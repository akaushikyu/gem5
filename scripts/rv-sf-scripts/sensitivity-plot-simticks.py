#!/usr/bin/python3
"""
plot_simticks_heatmap.py

Walks a directory tree collecting the `simTicks` stat from each `stats.txt`
found, for a specific (num-cpus, code-type, core-type, cache-levels)
configuration that also sweeps a secondary parameter (--param), and
renders a heatmap of normalized simTicks (deviation from the NOSF
baseline).

Supported sweep parameters
---------------------------
--param selects which secondary parameter the directories sweep over:

    rob      Reorder buffer size    valid values: [64, 256, 128, 192]
    l1mshr   L1 MSHR count          valid values: [1, 2, 4, 8, 12, 16]
    sq       Store queue size       valid values: [2, 4, 8, 12, 16]

Parsed values outside this list produce a warning (not an error), in case
a sweep has grown since this script was written.

Note: the "rob" parameter is not valid for --core-type minor (the Minor
CPU model doesn't have a configurable reorder buffer). Passing
--param rob --core-type minor raises an error.

Directory naming
-----------------
    SF variant (the "swept" runs, has a cbe OR tbe axis, plus the --param sweep):
        SF-<code_type>-bb-<bb>[-eb-<eb>|-rb-<rb>]-<core_type>-<cache_levels>-<cbe|tbe>-<n>-num-cpus-<num_cpus>-<param>-<value>
        e.g. SF-cr-bb-2-rb-4-minor-two-level-tbe-8-num-cpus-4-sq-8
             SF-cr-bb-2-rb-4-minor-two-level-cbe-4-num-cpus-4-rob-64   (o3-class core; rob is valid there)

    NOSF variant (the baseline, no cbe/tbe axis, still has the --param sweep):
        NOSF-<code_type>-bb-<bb>[-eb-<eb>|-rb-<rb>]-<core_type>-<cache_levels>-num-cpus-<num_cpus>-<param>-<value>
        e.g. NOSF-cr-bb-2-rb-4-minor-two-level-num-cpus-4-sq-8

Whether the "-eb-<eb>-" or "-rb-<rb>-" segment appears is tied directly to
code_type, exactly as in analyze_simticks.py:
    - code_type "cnr": has eb, never rb
    - code_type "cr":  has rb, never eb
    - code_type "uc" (or anything else): has neither eb nor rb

For a given (bb, rb, eb, <param value>), the NOSF directory's simTicks is
the baseline; every SF directory with that same (bb, rb, eb, <param value>)
is normalized against it (normalized_simTicks = SF simTicks / NOSF simTicks).

Heatmap
-------
The heatmap's rows are the <bb, rb/eb, axis> configuration (axis being
whichever of cbe/tbe you're sweeping, chosen with --axis), and its columns
are the swept --param values. Cell color encodes normalized_simTicks,
using a diverging colormap centered at 1.0 (green = faster than baseline,
red = slower). Any configuration with no simTicks value (directory
missing, or stats.txt unparseable) is rendered in solid black rather than
being given a color from the scale.

Usage:
    python plot_simticks_heatmap.py /path/to/root \\
        --num-cpus 4 --code-type cr --core-type minor --cache-levels two-level \\
        --param sq --axis tbe -o simticks.csv --plot-output simticks_heatmap.png

You can also import and call `collect_simticks(...)`, `normalize_simticks(...)`,
`build_heatmap_matrix(...)`, and `plot_heatmap(...)` directly from other code.
"""

import os
import re
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


# ----------------------------------------------------------------------
# Sweep parameter definitions
# ----------------------------------------------------------------------

PARAM_VALID_VALUES = {
    "rob": [64, 256, 128, 192],
    "l1mshr": [1, 2, 4, 8, 12, 16],
    "sq": [2, 4, 8, 12, 16],
}

# core_type values for which a given parameter doesn't apply.
PARAM_INVALID_CORE_TYPES = {
    "rob": {"minor"},
}


def validate_param(param, core_type):
    """Raise a clear error if param doesn't apply to core_type."""
    if param not in PARAM_VALID_VALUES:
        raise ValueError(f"Unknown --param {param!r}; expected one of {list(PARAM_VALID_VALUES)}.")
    invalid_core_types = PARAM_INVALID_CORE_TYPES.get(param, set())
    if core_type in invalid_core_types:
        raise ValueError(
            f"--param {param!r} is not valid for --core-type {core_type!r} "
            f"(not applicable to that core model)."
        )


def check_param_value(param, value):
    """Print a warning (not an error) if value isn't in the known-valid list."""
    valid = PARAM_VALID_VALUES.get(param)
    if valid is not None and value not in valid:
        print(f"Warning: parsed {param}={value}, which is outside the expected values {valid}.")


# ----------------------------------------------------------------------
# stats.txt parsing
# ----------------------------------------------------------------------

_NUMBER_RE = r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)"


def _to_number(value_str):
    """Convert a stats.txt value string to int (if whole) or float."""
    try:
        value = float(value_str)
    except ValueError:
        return value_str
    return int(value) if value.is_integer() else value


def parse_simticks(stats_path):
    """Return the simTicks value from a gem5 stats.txt file, or None."""
    pattern = re.compile(r"^(?:\S*\.)?simTicks\s+" + _NUMBER_RE, re.MULTILINE)
    try:
        with open(stats_path, "r", errors="ignore") as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    return _to_number(match.group(1))
    except (IOError, OSError):
        return None
    return None


# ----------------------------------------------------------------------
# Directory name matching
# ----------------------------------------------------------------------

def make_patterns(code_type, core_type, cache_levels, num_cpus, param):
    """
    Build compiled regexes for the SF and NOSF directory-naming variants,
    fixed to a specific code_type / core_type / cache_levels / num_cpus,
    sweeping the given `param` ("rob", "l1mshr", or "sq"). bb and the
    param value are always captured; eb/rb presence is tied to code_type
    ("cnr" -> eb, "cr" -> rb, anything else -> neither); the SF pattern
    additionally captures the cbe/tbe axis and its value.
    """
    core_tail = re.escape(core_type) + r"-" + re.escape(cache_levels)

    if code_type == "cnr":
        param_segment = r"eb-(?P<eb>\d+)-"
    elif code_type == "cr":
        param_segment = r"rb-(?P<rb>\d+)-"
    else:
        param_segment = r""

    sf_pattern = re.compile(
        r"^SF-" + re.escape(code_type) + r"-bb-(?P<bb>\d+)-" + param_segment + core_tail
        + r"-(?P<axis>cbe|tbe)-(?P<axis_value>\d+)-num-cpus-" + re.escape(str(num_cpus))
        + r"-" + re.escape(param) + r"-(?P<param_value>\d+)$"
    )
    nosf_pattern = re.compile(
        r"^NOSF-" + re.escape(code_type) + r"-bb-(?P<bb>\d+)-" + param_segment + core_tail
        + r"-num-cpus-" + re.escape(str(num_cpus))
        + r"-" + re.escape(param) + r"-(?P<param_value>\d+)$"
    )
    return sf_pattern, nosf_pattern


# ----------------------------------------------------------------------
# Small helpers for dealing with possibly-NaN config values
# ----------------------------------------------------------------------

def _key(v):
    """Turn a possibly-NaN numeric value into a hashable key (None if NaN)."""
    return None if pd.isna(v) else int(v)


def format_row_label(bb, rb, eb, axis_name, axis_value):
    """Human-readable row label, e.g. 'bb=2,rb=4,tbe=8'."""
    parts = [f"bb={int(bb)}"]
    if pd.notna(rb):
        parts.append(f"rb={int(rb)}")
    if pd.notna(eb):
        parts.append(f"eb={int(eb)}")
    parts.append(f"{axis_name}={int(axis_value)}")
    return ",".join(parts)


# ----------------------------------------------------------------------
# Collecting results
# ----------------------------------------------------------------------

def collect_simticks(root_dir, code_type, core_type, cache_levels, num_cpus, param):
    """
    Walk root_dir and build a DataFrame with columns:
        directory, bb, rb, eb, cbe, tbe, <param>, is_baseline, simTicks
    for every directory matching the SF or NOSF pattern for the given
    code_type / core_type / cache_levels / num_cpus / param.
    """
    validate_param(param, core_type)
    sf_pattern, nosf_pattern = make_patterns(code_type, core_type, cache_levels, num_cpus, param)

    records = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        if "stats.txt" not in filenames:
            continue

        dirname = os.path.basename(os.path.normpath(dirpath))
        sf_match = sf_pattern.match(dirname)
        nosf_match = nosf_pattern.match(dirname)

        if sf_match:
            bb = int(sf_match.group("bb"))
            eb = int(sf_match.group("eb")) if "eb" in sf_match.groupdict() and sf_match.group("eb") else np.nan
            rb = int(sf_match.group("rb")) if "rb" in sf_match.groupdict() and sf_match.group("rb") else np.nan
            param_value = int(sf_match.group("param_value"))
            axis = sf_match.group("axis")
            axis_value = int(sf_match.group("axis_value"))
            cbe = axis_value if axis == "cbe" else np.nan
            tbe = axis_value if axis == "tbe" else np.nan
            is_baseline = False
        elif nosf_match:
            bb = int(nosf_match.group("bb"))
            eb = int(nosf_match.group("eb")) if "eb" in nosf_match.groupdict() and nosf_match.group("eb") else np.nan
            rb = int(nosf_match.group("rb")) if "rb" in nosf_match.groupdict() and nosf_match.group("rb") else np.nan
            param_value = int(nosf_match.group("param_value"))
            cbe = np.nan
            tbe = np.nan
            is_baseline = True
        else:
            continue

        check_param_value(param, param_value)

        simticks = parse_simticks(os.path.join(dirpath, "stats.txt"))
        records.append({
            "directory": dirname,
            "bb": bb, "rb": rb, "eb": eb,
            "cbe": cbe, "tbe": tbe, param: param_value,
            "is_baseline": is_baseline,
            "simTicks": simticks,
        })

    df = pd.DataFrame(
        records,
        columns=["directory", "bb", "rb", "eb", "cbe", "tbe", param, "is_baseline", "simTicks"],
    )
    if df.empty:
        raise ValueError(
            f"No directories matched code_type={code_type!r}, core_type={core_type!r}, "
            f"cache_levels={cache_levels!r}, num_cpus={num_cpus}, param={param!r}. "
            "Check these values against your directory naming."
        )
    return df.sort_values(
        ["is_baseline", "bb", "rb", "eb", param, "cbe", "tbe"], na_position="first"
    ).reset_index(drop=True)


def normalize_simticks(df, param):
    """
    Given the DataFrame from collect_simticks, compute normalized_simTicks
    (SF simTicks / NOSF baseline simTicks for the same (bb, rb, eb, <param>))
    for every SF row.
    """
    key_cols = ["bb", "rb", "eb", param]
    baseline = df[df["is_baseline"]][key_cols + ["simTicks"]].copy()

    dup_mask = baseline.duplicated(subset=key_cols, keep=False)
    if dup_mask.any():
        dupes = baseline[dup_mask]
        print(
            "Warning: multiple NOSF (baseline) directories found for the same "
            f"(bb, rb, eb, {param}); averaging their simTicks:\n{dupes}"
        )
        baseline = baseline.groupby(key_cols, dropna=False, as_index=False)["simTicks"].mean()

    baseline = baseline.rename(columns={"simTicks": "baseline_simTicks"})

    sf_rows = df[~df["is_baseline"]].copy()
    merged = sf_rows.merge(baseline, on=key_cols, how="left")
    merged["normalized_simTicks"] = merged["simTicks"] / merged["baseline_simTicks"]

    missing = merged[merged["baseline_simTicks"].isna()][key_cols].drop_duplicates()
    if not missing.empty:
        print(
            f"Warning: no NOSF baseline found for these (bb, rb, eb, {param}) configs:\n"
            f"{missing}\nTheir normalized_simTicks will be NaN."
        )

    return merged.sort_values(
        ["bb", "rb", "eb", param, "cbe", "tbe"], na_position="first"
    ).reset_index(drop=True)


# ----------------------------------------------------------------------
# Heatmap data + rendering
# ----------------------------------------------------------------------

def build_heatmap_matrix(normalized_df, param, axis="tbe"):
    """
    Build a heatmap-ready pandas DataFrame from the normalized results:
        rows    -> one per (bb, rb, eb, axis_value) configuration
        columns -> swept `param` values
        values  -> normalized_simTicks (NaN where no data exists)

    `axis` selects which sweep ("cbe" or "tbe") to visualize; rows are
    labeled using format_row_label, e.g. "bb=2,rb=4,tbe=8".

    Returns (matrix_df, row_keys) where row_keys is a list of
    (bb, rb, eb, axis_value) tuples in the same order as matrix_df's rows,
    so callers can recover the raw config for each row if needed.
    """
    if axis not in ("cbe", "tbe"):
        raise ValueError("axis must be 'cbe' or 'tbe'")

    axis_rows = normalized_df.dropna(subset=[axis])
    if axis_rows.empty:
        raise ValueError(f"No rows found with a valid '{axis}' value to build the heatmap from.")

    row_keys = sorted(
        axis_rows[["bb", "rb", "eb", axis]].drop_duplicates().itertuples(index=False, name=None),
        key=lambda t: (t[0], 0 if pd.isna(t[1]) else 1, 0 if pd.isna(t[1]) else t[1],
                       0 if pd.isna(t[2]) else 1, 0 if pd.isna(t[2]) else t[2], t[3]),
    )
    row_labels = [format_row_label(bb, rb, eb, axis, val) for bb, rb, eb, val in row_keys]

    param_values = sorted(axis_rows[param].dropna().unique())

    lookup = {}
    for row in axis_rows.itertuples():
        axis_value = getattr(row, axis)
        param_value = getattr(row, param)
        key = (row.bb, _key(row.rb), _key(row.eb), _key(axis_value), _key(param_value))
        lookup[key] = row.normalized_simTicks

    data = []
    for bb, rb, eb, axis_value in row_keys:
        row_vals = [
            lookup.get((bb, _key(rb), _key(eb), _key(axis_value), _key(pv)), np.nan)
            for pv in param_values
        ]
        data.append(row_vals)

    matrix_df = pd.DataFrame(
        data, index=row_labels, columns=[f"{param}={int(pv)}" for pv in param_values]
    )
    return matrix_df, row_keys


def plot_heatmap(matrix_df, output_path=None, show=False,
                  num_cpus=None, code_type=None, core_type=None, cache_levels=None,
                  axis="tbe", param="rob"):
    """
    Render matrix_df (rows = configuration, columns = swept param) as a
    heatmap. Color encodes normalized_simTicks with a diverging scale
    centered at 1.0 (green = faster than baseline, red = slower). Missing
    values (NaN) are rendered solid black.
    """
    values = matrix_df.to_numpy(dtype=float)
    masked = np.ma.masked_invalid(values)

    finite_vals = values[np.isfinite(values)]
    if finite_vals.size == 0:
        raise ValueError("No finite normalized_simTicks values to plot; every cell is missing data.")

    vmin = min(finite_vals.min(), 0.999)
    vmax = max(finite_vals.max(), 1.001)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=1.0, vmax=vmax)

    cmap = plt.get_cmap("RdYlGn_r").copy()
    cmap.set_bad(color="black")

    n_rows, n_cols = values.shape
    fig_width = max(6, 0.9 * n_cols + 3)
    fig_height = max(4, 0.45 * n_rows + 2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    im = ax.imshow(masked, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(matrix_df.columns, rotation=45, ha="right")
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(matrix_df.index)

    # Gridlines between cells
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Annotate each cell
    for i in range(n_rows):
        for j in range(n_cols):
            val = values[i, j]
            if np.isnan(val):
                ax.text(j, i, "N/A", ha="center", va="center", fontsize=7, color="white")
            else:
                # Choose readable text color against the cell's background
                text_color = "black" if 0.35 < norm(val) < 0.75 else "white"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7, color=text_color)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Normalized simTicks (SF / NOSF baseline)")

    title = f"Normalized simTicks Heatmap ({axis.upper()} sweep)"
    subtitle_parts = []
    if num_cpus is not None:
        subtitle_parts.append(f"num-cpus={num_cpus}")
    if code_type is not None:
        subtitle_parts.append(code_type)
    if core_type is not None:
        subtitle_parts.append(core_type)
    if cache_levels is not None:
        subtitle_parts.append(cache_levels)
    if subtitle_parts:
        title += " (" + ", ".join(subtitle_parts) + ")"
    ax.set_title(title)
    ax.set_xlabel(param)
    ax.set_ylabel("Configuration (bb, rb/eb, " + axis + ")")

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved heatmap to {output_path}")
    if show:
        plt.show()
    plt.close(fig)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collect simTicks across a (bb, rb/eb, cbe/tbe, <param>) sweep and plot a normalized heatmap."
    )
    parser.add_argument("root_dir", help="Root directory to search recursively.")
    parser.add_argument("--num-cpus", type=int, required=True, help="The num-cpus value to filter on.")
    parser.add_argument("--code-type", required=True, help="Code type to filter on, e.g. 'uc', 'cnr', 'cr'.")
    parser.add_argument("--core-type", required=True, help="Core type to filter on, e.g. 'minor', 'o3'.")
    parser.add_argument("--cache-levels", required=True, help="Cache levels to filter on, e.g. 'one-level', 'two-level'.")
    parser.add_argument("--param", choices=list(PARAM_VALID_VALUES), required=True,
                         help="Which secondary sweep parameter the directories vary (forms the heatmap columns). "
                              "Note: 'rob' is not valid together with --core-type minor.")
    parser.add_argument("--axis", choices=["cbe", "tbe"], default="tbe",
                         help="Which sweep axis to visualize in the heatmap rows (default: tbe).")
    parser.add_argument("-o", "--output", default=None, help="Optional path to save the normalized results as CSV.")
    parser.add_argument("--plot-output", default="simticks_heatmap.png", help="Output image path for the heatmap.")
    args = parser.parse_args()

    df = collect_simticks(args.root_dir, args.code_type, args.core_type, args.cache_levels, args.num_cpus, args.param)
    print("Raw collected data:")
    print(df)

    normalized = normalize_simticks(df, args.param)
    normalized_indexed = normalized.set_index(["bb", "rb", "eb", args.param])
    print(f"\nNormalized data (indexed by bb, rb, eb, {args.param}):")
    print(normalized_indexed)

    if args.output:
        normalized_indexed.to_csv(args.output)
        print(f"\nSaved normalized results to {args.output}")

    matrix_df, _row_keys = build_heatmap_matrix(normalized, args.param, axis=args.axis)
    print(f"\nHeatmap matrix ({args.axis} sweep, columns = {args.param}):")
    print(matrix_df)

    plot_heatmap(
        matrix_df,
        output_path=args.plot_output,
        num_cpus=args.num_cpus,
        code_type=args.code_type,
        core_type=args.core_type,
        cache_levels=args.cache_levels,
        axis=args.axis,
        param=args.param,
    )


if __name__ == "__main__":
    main()

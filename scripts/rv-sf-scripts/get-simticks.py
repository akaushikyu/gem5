#!/usr/bin/env python3
"""
analyze_simticks.py

Walks a directory tree collecting the `simTicks` stat from each `stats.txt`
found, for a specific (num-cpus, code-type, core-type, cache-levels)
configuration, and builds a pandas DataFrame of the results.

Directory naming
-----------------
Two top-level naming conventions are recognized:

    SF variant (the "swept" runs, has a cbe OR tbe axis):
        SF-<code_type>-bb-<bb>[-eb-<eb>|-rb-<rb>]-<core_type>-<cache_levels>-<cbe|tbe>-<n>-num-cpus-<num_cpus>

    NOSF variant (the baseline, no cbe/tbe axis):
        NOSF-<code_type>-bb-<bb>[-eb-<eb>|-rb-<rb>]-<core_type>-<cache_levels>-num-cpus-<num_cpus>

Whether the "-eb-<eb>-" or "-rb-<rb>-" segment appears is tied directly to
code_type -- each code_type has exactly one fixed shape:

    - code_type "cnr":  SF-cnr-bb-2-eb-4-minor-two-level-cbe-4-num-cpus-4
                         -> eb=4, rb=None
    - code_type "cr":   SF-cr-bb-2-rb-4-minor-two-level-cbe-4-num-cpus-4
                         -> rb=4, eb=None
    - code_type "uc"
      (or any other):   SF-uc-bb-2-minor-two-level-cbe-4-num-cpus-4
                         -> rb=None, eb=None (the "uc" flavor never has an
                            eb or rb segment in the directory name)

Resulting DataFrame
--------------------
Every collected/normalized DataFrame is indexed by the tuple (bb, rb, eb)
-- rb is NaN for "uc"/"cnr" runs, eb is NaN for "uc"/"cr" runs. cbe/tbe
stay as regular columns (one of them populated per SF row) since a given
(bb, rb, eb) configuration typically has many cbe or tbe data points.

For a given (bb, rb, eb), the NOSF directory's simTicks is treated as the
baseline, and every SF directory with that same (bb, rb, eb) is normalized
against it (normalized_simTicks = SF simTicks / NOSF simTicks).

Usage:
    # Just build and print/save the normalized DataFrame
    python analyze_simticks.py /path/to/root \\
        --num-cpus 4 --code-type uc --core-type minor --cache-levels two-level \\
        -o simticks.csv

    # Also render a normalized bar chart (CBE sweep) and a max/min chart (CBE vs TBE)
    python analyze_simticks.py /path/to/root \\
        --num-cpus 4 --code-type cr --core-type minor --cache-levels two-level \\
        -o simticks.csv --plot --plot-output simticks_normalized.png \\
        --plot-minmax --minmax-output simticks_minmax.png

You can also import and call `collect_simticks(...)`, `normalize_simticks(...)`,
`compute_minmax_simticks(...)`, `plot_normalized_bar_chart(...)`, and
`plot_minmax_bar_chart(...)` directly from other code.
"""

import os
import re
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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

def make_patterns(code_type, core_type, cache_levels, num_cpus):
    """
    Build compiled regexes for the SF and NOSF directory-naming variants,
    fixed to a specific code_type / core_type / cache_levels / num_cpus.
    bb is always captured; eb and rb are optional and mutually exclusive;
    the SF pattern additionally captures the cbe/tbe axis and its value.
    """
    optional_eb_rb = r"(?:eb-(?P<eb>\d+)-)?(?:rb-(?P<rb>\d+)-)?"
    tail = re.escape(core_type) + r"-" + re.escape(cache_levels)

    sf_pattern = re.compile(
        r"^SF-" + re.escape(code_type) + r"-bb-(?P<bb>\d+)-" + optional_eb_rb + tail
        + r"-(?P<axis>cbe|tbe)-(?P<axis_value>\d+)-num-cpus-" + re.escape(str(num_cpus)) + r"$"
    )
    nosf_pattern = re.compile(
        r"^NOSF-" + re.escape(code_type) + r"-bb-(?P<bb>\d+)-" + optional_eb_rb + tail
        + r"-num-cpus-" + re.escape(str(num_cpus)) + r"$"
    )
    return sf_pattern, nosf_pattern


# ----------------------------------------------------------------------
# Small helpers for dealing with the (bb, rb, eb) config key, where rb/eb
# may be NaN.
# ----------------------------------------------------------------------

def _key(v):
    """Turn a possibly-NaN numeric value into a hashable key (None if NaN)."""
    return None if pd.isna(v) else int(v)


def format_config_label(bb, rb, eb):
    """Human-readable label for a (bb, rb, eb) configuration, e.g. 'bb=2,rb=4'."""
    parts = [f"bb={int(bb)}"]
    if pd.notna(rb):
        parts.append(f"rb={int(rb)}")
    if pd.notna(eb):
        parts.append(f"eb={int(eb)}")
    return ",".join(parts)


def get_sorted_configs(df):
    """
    Return the sorted, deduplicated list of (bb, rb, eb) tuples present in
    df, ordered by bb, then plain < rb-flavor < eb-flavor, then value.
    """
    configs = df[["bb", "rb", "eb"]].drop_duplicates().reset_index(drop=True)

    def sort_key(row):
        bb, rb, eb = row["bb"], row["rb"], row["eb"]
        if pd.isna(rb) and pd.isna(eb):
            return (bb, 0, 0)
        if pd.notna(rb):
            return (bb, 1, rb)
        return (bb, 2, eb)

    keys = configs.apply(sort_key, axis=1)
    order = sorted(range(len(configs)), key=lambda i: keys[i])
    configs = configs.iloc[order].reset_index(drop=True)
    return list(configs.itertuples(index=False, name=None))


# ----------------------------------------------------------------------
# Collecting results
# ----------------------------------------------------------------------

def collect_simticks(root_dir, code_type, core_type, cache_levels, num_cpus):
    """
    Walk root_dir and build a DataFrame with columns:
        directory, bb, rb, eb, cbe, tbe, is_baseline, simTicks
    for every directory matching the SF or NOSF pattern for the given
    code_type / core_type / cache_levels / num_cpus.

    rb is NaN for plain and "cnr"-flavored (eb-based) directories.
    eb is NaN for plain and "cr"-flavored (rb-based) directories.
    For SF rows exactly one of cbe/tbe is populated; for NOSF (baseline)
    rows both are NaN.
    """
    sf_pattern, nosf_pattern = make_patterns(code_type, core_type, cache_levels, num_cpus)

    records = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        if "stats.txt" not in filenames:
            continue

        dirname = os.path.basename(os.path.normpath(dirpath))
        sf_match = sf_pattern.match(dirname)
        nosf_match = nosf_pattern.match(dirname)

        if sf_match:
            bb = int(sf_match.group("bb"))
            eb = int(sf_match.group("eb")) if sf_match.group("eb") else np.nan
            rb = int(sf_match.group("rb")) if sf_match.group("rb") else np.nan
            axis = sf_match.group("axis")
            axis_value = int(sf_match.group("axis_value"))
            cbe = axis_value if axis == "cbe" else np.nan
            tbe = axis_value if axis == "tbe" else np.nan
            is_baseline = False
        elif nosf_match:
            bb = int(nosf_match.group("bb"))
            eb = int(nosf_match.group("eb")) if nosf_match.group("eb") else np.nan
            rb = int(nosf_match.group("rb")) if nosf_match.group("rb") else np.nan
            cbe = np.nan
            tbe = np.nan
            is_baseline = True
        else:
            continue

        simticks = parse_simticks(os.path.join(dirpath, "stats.txt"))
        records.append({
            "directory": dirname,
            "bb": bb, "rb": rb, "eb": eb,
            "cbe": cbe, "tbe": tbe,
            "is_baseline": is_baseline,
            "simTicks": simticks,
        })

    df = pd.DataFrame(
        records,
        columns=["directory", "bb", "rb", "eb", "cbe", "tbe", "is_baseline", "simTicks"],
    )
    if df.empty:
        raise ValueError(
            f"No directories matched code_type={code_type!r}, core_type={core_type!r}, "
            f"cache_levels={cache_levels!r}, num_cpus={num_cpus}. "
            "Check these values against your directory naming."
        )
    return df.sort_values(
        ["is_baseline", "bb", "rb", "eb", "cbe", "tbe"], na_position="first"
    ).reset_index(drop=True)


def normalize_simticks(df):
    """
    Given the DataFrame from collect_simticks, compute normalized_simTicks
    (SF simTicks / NOSF baseline simTicks for the same (bb, rb, eb)) for
    every SF row.

    Returns a DataFrame of just the SF rows with added 'baseline_simTicks'
    and 'normalized_simTicks' columns. bb/rb/eb remain as plain columns
    (not yet the index) so the result can still be grouped/filtered easily;
    callers that want the (bb, rb, eb)-indexed DataFrame described in the
    module docstring can call `.set_index(["bb", "rb", "eb"])` on the result.
    """
    key_cols = ["bb", "rb", "eb"]
    baseline = df[df["is_baseline"]][key_cols + ["simTicks"]].copy()

    dup_mask = baseline.duplicated(subset=key_cols, keep=False)
    if dup_mask.any():
        dupes = baseline[dup_mask]
        print(
            "Warning: multiple NOSF (baseline) directories found for the same "
            f"(bb, rb, eb); averaging their simTicks:\n{dupes}"
        )
        baseline = baseline.groupby(key_cols, dropna=False, as_index=False)["simTicks"].mean()

    baseline = baseline.rename(columns={"simTicks": "baseline_simTicks"})

    sf_rows = df[~df["is_baseline"]].copy()
    merged = sf_rows.merge(baseline, on=key_cols, how="left")
    merged["normalized_simTicks"] = merged["simTicks"] / merged["baseline_simTicks"]

    missing = merged[merged["baseline_simTicks"].isna()][key_cols].drop_duplicates()
    if not missing.empty:
        print(
            "Warning: no NOSF baseline found for these (bb, rb, eb) configs:\n"
            f"{missing}\nTheir normalized_simTicks will be NaN."
        )

    return merged.sort_values(
        ["bb", "rb", "eb", "cbe", "tbe"], na_position="first"
    ).reset_index(drop=True)


def compute_minmax_simticks(normalized_df):
    """
    Given the normalized DataFrame, compute the maximum and minimum
    normalized_simTicks for each (bb, rb, eb) configuration, separately for
    the CBE sweep and the TBE sweep.

    Returns a "long format" DataFrame with one row per (bb, rb, eb, axis,
    stat) combination, columns:
        bb, rb, eb, axis ("CBE" or "TBE"), stat ("max" or "min"),
        normalized_simTicks, param_value (the cbe/tbe value that produced it)
    A configuration with no directories for a given axis simply has no rows
    for that axis.
    """
    records = []
    grouped = normalized_df.groupby(["bb", "rb", "eb"], dropna=False)
    for (bb, rb, eb), group in grouped:
        g = group.dropna(subset=["normalized_simTicks"])
        for axis_name, col in (("CBE", "cbe"), ("TBE", "tbe")):
            axis_group = g.dropna(subset=[col])
            if axis_group.empty:
                continue
            max_row = axis_group.loc[axis_group["normalized_simTicks"].idxmax()]
            min_row = axis_group.loc[axis_group["normalized_simTicks"].idxmin()]
            records.append({
                "bb": bb, "rb": rb, "eb": eb, "axis": axis_name, "stat": "max",
                "normalized_simTicks": max_row["normalized_simTicks"],
                "param_value": max_row[col],
            })
            records.append({
                "bb": bb, "rb": rb, "eb": eb, "axis": axis_name, "stat": "min",
                "normalized_simTicks": min_row["normalized_simTicks"],
                "param_value": min_row[col],
            })

    if not records:
        raise ValueError(
            "No rows with a valid normalized_simTicks and a cbe or tbe value "
            "were found to compute min/max from."
        )

    return pd.DataFrame(records).sort_values(["bb", "rb", "eb", "axis", "stat"], na_position="first").reset_index(drop=True)


# ----------------------------------------------------------------------
# Plotting
# ----------------------------------------------------------------------

def _title_suffix(num_cpus, code_type, core_type, cache_levels):
    parts = []
    if num_cpus is not None:
        parts.append(f"num-cpus={num_cpus}")
    if code_type is not None:
        parts.append(code_type)
    if core_type is not None:
        parts.append(core_type)
    if cache_levels is not None:
        parts.append(cache_levels)
    return " (" + ", ".join(parts) + ")" if parts else ""


def plot_normalized_bar_chart(normalized_df, output_path=None, show=False,
                               num_cpus=None, code_type=None, core_type=None, cache_levels=None):
    """
    Render a grouped bar chart of normalized_simTicks (CBE sweep only),
    with one x-axis group per (bb, rb, eb) configuration and one bar per
    cbe value within each group, plus a dashed reference line at y=1.0
    (the NOSF baseline).
    """
    cbe_rows = normalized_df.dropna(subset=["cbe"])
    if cbe_rows.empty:
        raise ValueError(
            "No CBE-sweep rows found to plot (this chart shows the CBE sweep only; "
            "TBE-only data won't appear here)."
        )

    configs = get_sorted_configs(cbe_rows)
    config_labels = [format_config_label(*c) for c in configs]
    n_configs = len(configs)

    cbe_values = sorted(cbe_rows["cbe"].dropna().unique())
    n_cbe = len(cbe_values)

    lookup = {}
    for row in cbe_rows.itertuples():
        lookup[(row.bb, _key(row.rb), _key(row.eb), _key(row.cbe))] = row.normalized_simTicks

    group_width = 0.8
    bar_width = group_width / max(n_cbe, 1)
    fig_width = max(6, 1.2 * n_configs * max(n_cbe, 1) + 2)
    fig, ax = plt.subplots(figsize=(fig_width, 5))
    cmap = plt.get_cmap("tab10")

    for j, cbe in enumerate(cbe_values):
        heights = [lookup.get((bb, _key(rb), _key(eb), _key(cbe)), np.nan) for bb, rb, eb in configs]
        offsets = [i - group_width / 2 + bar_width / 2 + j * bar_width for i in range(n_configs)]
        ax.bar(offsets, heights, width=bar_width * 0.95, label=f"cbe={cbe:g}", color=cmap(j % 10))

    ax.axhline(1.0, color="black", linestyle="--", linewidth=1, label="Baseline (NOSF)")

    ax.set_xticks(range(n_configs))
    ax.set_xticklabels(config_labels, rotation=45, ha="right")
    ax.set_xlabel("Configuration (bb, rb, eb)")
    ax.set_ylabel("Normalized simTicks (SF / NOSF baseline)")
    ax.set_title("Normalized simTicks - CBE sweep" + _title_suffix(num_cpus, code_type, core_type, cache_levels))

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved bar chart to {output_path}")
    if show:
        plt.show()
    plt.close(fig)


def plot_minmax_bar_chart(minmax_df, output_path=None, show=False,
                           num_cpus=None, code_type=None, core_type=None, cache_levels=None):
    """
    Render a grouped bar chart with 4 bars per (bb, rb, eb) configuration:
    CBE Max, CBE Min, TBE Max, TBE Min (any missing for a given
    configuration are simply skipped), with a dashed reference line at
    y=1.0 (the baseline). Each bar is annotated with the cbe/tbe value that
    produced it.
    """
    configs = get_sorted_configs(minmax_df)
    config_labels = [format_config_label(*c) for c in configs]
    n_configs = len(configs)

    series = [
        ("CBE", "max", "CBE Max", "#d9534f"),
        ("CBE", "min", "CBE Min", "#5cb85c"),
        ("TBE", "max", "TBE Max", "#f0ad4e"),
        ("TBE", "min", "TBE Min", "#5bc0de"),
    ]
    n_series = len(series)

    group_width = 0.8
    bar_width = group_width / n_series
    fig_width = max(6, 1.6 * n_configs + 2)
    fig, ax = plt.subplots(figsize=(fig_width, 5))
    x = np.arange(n_configs)

    lookup = {}
    for row in minmax_df.itertuples():
        lookup[(row.bb, _key(row.rb), _key(row.eb), row.axis, row.stat)] = (
            row.normalized_simTicks, row.param_value
        )

    for k, (axis_name, stat_name, label, color) in enumerate(series):
        offsets = x - group_width / 2 + bar_width / 2 + k * bar_width
        heights, param_values = [], []
        for bb, rb, eb in configs:
            entry = lookup.get((bb, _key(rb), _key(eb), axis_name, stat_name))
            if entry is None:
                heights.append(np.nan)
                param_values.append(None)
            else:
                heights.append(entry[0])
                param_values.append(entry[1])

        bars = ax.bar(offsets, heights, width=bar_width * 0.95, label=label, color=color)

        for bar, height, param_value in zip(bars, heights, param_values):
            if param_value is None or np.isnan(height):
                continue
            tag = f"{axis_name.lower()}={param_value:g}"
            ax.text(bar.get_x() + bar.get_width() / 2, height, tag,
                    ha="center", va="bottom", fontsize=7, rotation=90)

    ax.axhline(1.0, color="black", linestyle="--", linewidth=1, label="Baseline (NOSF)")

    ax.set_xticks(x)
    ax.set_xticklabels(config_labels, rotation=45, ha="right")
    ax.set_xlabel("Configuration (bb, rb, eb)")
    ax.set_ylabel("Normalized simTicks (SF / NOSF baseline)")
    ax.set_title(
        "Max / Min Normalized simTicks per Configuration (CBE vs TBE)"
        + _title_suffix(num_cpus, code_type, core_type, cache_levels)
    )

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved min/max bar chart to {output_path}")
    if show:
        plt.show()
    plt.close(fig)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collect simTicks across a directory sweep and optionally plot normalized results."
    )
    parser.add_argument("root_dir", help="Root directory to search recursively.")
    parser.add_argument("--num-cpus", type=int, required=True, help="The num-cpus value to filter on.")
    parser.add_argument("--code-type", required=True, help="Code type to filter on, e.g. 'uc', 'cnr'.")
    parser.add_argument("--core-type", required=True, help="Core type to filter on, e.g. 'minor', 'o3'.")
    parser.add_argument("--cache-levels", required=True, help="Cache levels to filter on, e.g. 'one-level', 'two-level'.")
    parser.add_argument("-o", "--output", default=None, help="Optional path to save the normalized results as CSV.")
    parser.add_argument("--plot", action="store_true", help="Also render a normalized bar chart (CBE sweep).")
    parser.add_argument("--plot-output", default="simticks_normalized.png", help="Output image path for the bar chart.")
    parser.add_argument("--plot-minmax", action="store_true",
                         help="Also render a bar chart of the max/min normalized simTicks per (bb, rb, eb) "
                              "configuration, with separate bars for the CBE sweep and the TBE sweep.")
    parser.add_argument("--minmax-output", default="simticks_minmax.png",
                         help="Output image path for the max/min bar chart.")
    args = parser.parse_args()

    df = collect_simticks(args.root_dir, args.code_type, args.core_type, args.cache_levels, args.num_cpus)
    print("Raw collected data:")
    print(df)

    normalized = normalize_simticks(df)

    # Present/save the normalized results indexed by (bb, rb, eb), as requested.
    normalized_indexed = normalized.set_index(["bb", "rb", "eb"])
    print("\nNormalized data (indexed by bb, rb, eb):")
    print(normalized_indexed)

    if args.output:
        normalized_indexed.to_csv(args.output)
        print(f"\nSaved normalized results to {args.output}")

    if args.plot:
        plot_normalized_bar_chart(
            normalized,
            output_path=args.plot_output,
            num_cpus=args.num_cpus,
            code_type=args.code_type,
            core_type=args.core_type,
            cache_levels=args.cache_levels,
        )

    if args.plot_minmax:
        minmax = compute_minmax_simticks(normalized)
        print("\nMax/min normalized simTicks per (bb, rb, eb):")
        print(minmax.set_index(["bb", "rb", "eb"]))
        plot_minmax_bar_chart(
            minmax,
            output_path=args.minmax_output,
            num_cpus=args.num_cpus,
            code_type=args.code_type,
            core_type=args.core_type,
            cache_levels=args.cache_levels,
        )


if __name__ == "__main__":
    main()

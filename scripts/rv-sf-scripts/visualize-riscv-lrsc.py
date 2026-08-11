#!/usr/bin/python3
"""
visualize_success_matrix.py

Reads the results CSV produced by extract_gem5_results.py (columns:
directory, success, simTicks, LLIssued, SCIssued, SCFailed) and renders a
color-coded matrix (green = success, red = failure) for a single
num-cpus configuration.

Directory names are expected to follow this pattern:
    SF-<code_type>-bb-<bb>-<core_type>-<cache_levels>-<ee_type>-<ee>-num-cpus-<num_cpus>
e.g.
    SF-uc-bb-2-minor-two-level-cbe-4-num-cpus-4

code_type (e.g. "uc"), core_type (e.g. "minor", "o3"), and cache_levels
(e.g. "one-level", "two-level") are passed on the command line so you can
filter down to exactly the sweep you want to visualize.

The matrix axes are:
    rows    -> bb   (number of blobs)
    columns -> ee  (configuration)
filtered down to a single num-cpus value, code_type, core_type, and
cache_levels combination, all chosen on the command line.

Usage:
    python visualize_success_matrix.py results.csv \\
        --num-cpus 4 --code-type uc --core-type minor --cache-levels two-level \\
        -o matrix.png

You can also import and call `build_matrix(df, num_cpus, code_type, core_type,
cache_levels)` and `plot_matrix(matrix, num_cpus, output_path)` directly from
other code.
"""

import re
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


def make_dir_pattern(ee_type, code_type, core_type, cache_levels):
    """
    Build a compiled regex that matches directory names of the form:
        SF-<code_type>-bb-<bb>-<core_type>-<cache_levels>-<ee_type>-<ee>-num-cpus-<num_cpus>
    for the specific code_type / core_type / cache_levels given, and
    captures bb, ee, and num_cpus as named groups.
    """
    if (code_type == "uc"):
        return re.compile(
            r"SF-" + re.escape(code_type) +
            r"-bb-(?P<bb>\d+)-" + re.escape(core_type) +
            r"-" + re.escape(cache_levels) +
            r"-" + re.escape(ee_type) +
            r"-(?P<ee_type>\d+)-num-cpus-(?P<num_cpus>\d+)"
        )
    elif (code_type == "cnr"):
        return re.compile(
            r"SF-" + re.escape(code_type) +
            r"-bb-(?P<bb>\d+)-eb-(?P<eb>\d+)-" + re.escape(core_type) +
            r"-" + re.escape(cache_levels) +
            r"-" + re.escape(ee_type) +
            r"-(?P<ee_type>\d+)-num-cpus-(?P<num_cpus>\d+)"
        )
    else:
        return re.compile(
            r"SF-" + re.escape(code_type) +
            r"-bb-(?P<bb>\d+)-rb-(?P<rb>\d+)-" + re.escape(core_type) +
            r"-" + re.escape(cache_levels) +
            r"-" + re.escape(ee_type) +
            r"-(?P<ee_type>\d+)-num-cpus-(?P<num_cpus>\d+)"
        )

def parse_directory_name(code_type, dirname, dir_pattern):
    """
    Extract (bb, ee, num_cpus) as ints from a directory name using the
    given compiled dir_pattern (see make_dir_pattern).
    Returns None if the name doesn't match.
    """
    #print (f"dir_pattern {dir_pattern}")
    match = dir_pattern.search(dirname)
    if not match:
        return None
    if (code_type == "uc"):
        return (
            int(match.group("bb")),
            None,
            None,
            int(match.group("ee_type")),
            int(match.group("num_cpus")),
        )
    elif (code_type == "cnr"):
        return (
            int(match.group("bb")),
            None,
            int(match.group("eb")),
            int(match.group("ee_type")),
            int(match.group("num_cpus")),
        )
    else:
        return (
            int(match.group("bb")),
            int(match.group("rb")),
            None,
            int(match.group("ee_type")),
            int(match.group("num_cpus")),
        )

def build_matrix(df, num_cpus, ee_type, code_type, core_type, cache_levels):
    """
    Given the results DataFrame (with a 'directory' column or index, and a
    'success' column), a target num_cpus, and the code_type / core_type /
    cache_levels filters, build a bb x ee matrix of success values
    (True/False/NaN) for that specific configuration.

    Returns a pandas DataFrame indexed by bb, with ee as columns, sorted
    numerically on both axes.
    """
    dir_pattern = make_dir_pattern(ee_type, code_type, core_type, cache_levels)

    # Support either 'directory' as a column or as the index.
    if "directory" in df.columns:
        dir_series = df["directory"]
    else:
        dir_series = df.index.to_series()

    rows = []
    for dirname, success in zip(dir_series, df["success"]):
        parsed = parse_directory_name(code_type, str(dirname), dir_pattern)
        if parsed is None:
            continue
        bb, rb, eb, ee, cpus = parsed
        if cpus != num_cpus:
            continue
        rows.append({"bb": bb, "rb": rb, "eb": eb, "ee": ee, "success": success})

    if not rows:
        raise ValueError(
            f"No directories matched code_type={code_type!r}, core_type={core_type!r}, "
            f"cache_levels={cache_levels!r}, num_cpus={num_cpus}. "
            "Check these values against your directory naming."
        )

    parsed_df = pd.DataFrame(rows)

    # If there are duplicate (bb, ee) entries, keep the last one and warn.
    if parsed_df.duplicated(subset=["bb", "rb", "eb", "ee"]).any():
        dupes = parsed_df[parsed_df.duplicated(subset=["bb", "rb", "eb", "ee"], keep=False)]

        print(
            "Warning: multiple directories map to the same (bb, ee) pair for "
            f"num-cpus={num_cpus}; keeping the last one for each:\n{dupes}"
        )
        parsed_df = parsed_df.drop_duplicates(subset=["bb", "rb", "eb", "ee"], keep="last")


    matrix = parsed_df.pivot(index=["bb", "rb", "eb"], columns="ee", values="success")
    matrix = matrix.sort_index(axis=0).sort_index(axis=1)
    return matrix


def plot_matrix(matrix, num_cpus, output_path=None, show=False, config_label=None):
    """
    Render the bb x ee success matrix as a color-coded grid:
        green = success, red = failure, light gray = missing/no data.
    """
    # Map True/False/NaN -> 1/0/-1 for coloring
    def _to_numeric(v):
        return 1 if v is True else (0 if v is False else np.nan)

    #if hasattr(matrix, "map"):
    #    numeric = matrix.map(_to_numeric)
    #else:  # pandas < 2.1 fallback
    #    numeric = matrix.applymap(_to_numeric)

    #cmap -- green for pass,
    #        pink for SC failure,
    #        red for time limit reached
    #        black for aborted string
    #        white for everything else
    cmap = ListedColormap(["#5cb85c","#f700a9","#d90000","#010000","#f7fcfa"])
    #cmap = ListedColormap(["#d9534f", "#5cb85c"])  # 0 -> red, 1 -> green
    cmap.set_bad(color="#e0e0e0")  # NaN -> light gray

    masked = np.ma.masked_invalid(matrix.values)

    fig_width = max(4, 0.6 * len(matrix.columns) + 2)
    fig_height = max(3, 0.6 * len(matrix.index) + 2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    ax.imshow(masked, cmap=cmap, vmin=0, vmax=4, aspect="auto")

    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns)
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)

    ax.set_xlabel("ee (configuration)")
    ax.set_ylabel("<bb,rb,eb> (number of blobs, rb, eb)")
    title = f"Success / Failure Matrix (num-cpus = {num_cpus}"
    title += f", {config_label})" if config_label else ")"
    ax.set_title(title)

    # Gridlines between cells
    ax.set_xticks(np.arange(-0.5, len(matrix.columns), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(matrix.index), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Annotate each cell with PASS/FAIL/N/A
    for i, bb in enumerate(matrix.index):
        for j, ee in enumerate(matrix.columns):
            val = matrix.loc[bb, ee]
            if val == 0:
                text = "PASS"
            elif val == 1:
                text = "FAIL"
            elif val == 2:
                text = "OT"
            else:
                text = "ABT"
            ax.text(j, i, text, ha="center", va="center", fontsize=6, fontweight="bold",
                     color="white" if text in ("PASS", "FAIL", "OT", "ABT") else "black")

    cmap = ListedColormap(["#5cb85c","#f700a9","#d90000","#010000","#f7fcfa"])
    legend_elements = [
        Patch(facecolor="#5cb85c", label="Success"),
        Patch(facecolor="#f700a9", label="Failure (starvation freedom)"),
        Patch(facecolor="#d90000", label="Overrun simulation time (FATAL)"),
        Patch(facecolor="#010000", label="Aborted (FATAL)"),
        Patch(facecolor="#f7fcfa", label="No data"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", bbox_to_anchor=(1.02, 1.0))

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved matrix plot to {output_path}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize success/failure as a bb x ee matrix for a given configuration."
    )
    parser.add_argument("csv_path", help="Path to the results CSV (from extract_gem5_results.py).")
    parser.add_argument(
        "--num-cpus", type=int, required=True, help="The num-cpus value to filter on."
    )
    parser.add_argument(
            "--ee-type", required=True, help="Execution environment type e.g cbe|tbe."
    )
    parser.add_argument(
        "--code-type", required=True, help="Code type to filter on, e.g. 'uc|cr|ncr'."
    )
    parser.add_argument(
        "--core-type", required=True, help="Core type to filter on, e.g. 'minor', 'o3'."
    )
    parser.add_argument(
        "--cache-levels", required=True, help="Cache levels to filter on, e.g. 'one-level', 'two-level'."
    )
    parser.add_argument(
        "-o", "--output", default="success_matrix.png", help="Output image path (default: success_matrix.png)."
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)

    # Normalize the success column: CSV round-trip can turn True/False into
    # strings ("True"/"False") depending on how it was written.
    if df["success"].dtype == object:
        df["success"] = df["success"].map(
            {"True": True, "False": False, True: True, False: False}
        )

    matrix = build_matrix(
        df, args.num_cpus, args.ee_type, args.code_type, args.core_type, args.cache_levels
    )
    print(matrix)

    config_label = f"{args.code_type}, {args.core_type}, {args.cache_levels}"
    plot_matrix(matrix, args.num_cpus, output_path=args.output, config_label=config_label)


if __name__ == "__main__":
    main()

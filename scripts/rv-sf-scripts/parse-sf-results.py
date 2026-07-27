#!/usr/bin/env python3
"""
extract_gem5_results.py

Walks a directory tree looking for pairs of files in the same directory:
    - simout.txt   -> checked for the success marker string
    - stats.txt    -> parsed for gem5 stat values:
                         * simTicks              (single, system-wide stat)
                         * LLIssued, SCIssued,
                           SCFailed               (per-core stats, summed
                                                    across all cores)

Per-core stats appear in stats.txt once per CPU, e.g.:
    system.cpu0.lsq0.LLIssued
    system.cpu1.lsq0.LLIssued
    system.cpu0.lsq0.SCIssued   (this is the "SCIssued" stat)
    system.cpu1.lsq0.SCIssued
    system.cpu0.lsq0.SCFailed
    system.cpu1.lsq0.SCFailed
This script finds every core's value for each of these stats and sums them
to produce a single system-wide total per stat.

Results are collected into a pandas DataFrame indexed by directory (path).

Usage:
    python extract_gem5_results.py /path/to/root [-o results.csv]

You can also import and call `collect_results(root_dir)` directly from other code.
"""

import os
import re
import argparse
import pandas as pd

# The exact success string we're looking for in simout.txt
SUCCESS_STRING = "Done. g_counter final value"

# Scalar (system-wide, appears once) stats to pull out of stats.txt.
# Keys are the column names used in the DataFrame; values are the
# stat-name fragments to search for.
SCALAR_STATS = {
    "simTicks": "simTicks",

}

# Per-core stats: these appear once per CPU as
# system.cpu<i>.lsq0.<stat_name>, and are summed across all cores.
# Keys are the column names used in the DataFrame; values are the actual
# stat name as it appears in stats.txt after "lsq0.".
PER_CORE_STATS = {
    "LLIssued": "LLIssued",
    "SCIssued": "SCIssued",
    "SCFailed": "SCFailed",
}

DIRECTORY_NAME_STATS = {
    "mode": "mode",
    "lrsc-type": "lrsc-type",
    "blobs-between": "blobs-between",
    "condition-type": "condition-type",
    "blobs-exit-retry": "blobs-exit-retry",
    "cpu-type": "cpu-type",
    "cache-levels": "cache-levels",
    "ee-type": "ee-type",
    "ee-config": "ee-config",
    "num-cpus": "num-cpus", 
}


def check_simout(simout_path):
    """Return True if SUCCESS_STRING is found in simout.txt, else False."""
    try:
        with open(simout_path, "r", errors="ignore") as f:
            content = f.read()
        return SUCCESS_STRING in content
    except (IOError, OSError):
        return None


_NUMBER_RE = r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)"


def _to_number(value_str):
    """Convert a stats.txt value string to int (if whole) or float."""
    try:
        value = float(value_str)
    except ValueError:
        return value_str
    if value.is_integer():
        return int(value)
    return value


def parse_stats(stats_path, scalar_stats, per_core_stats, cpu_type):
    """
    Parse a gem5 stats.txt file and pull out the requested stats.

    gem5 stats.txt lines generally look like:
        simTicks                                   123456789  # description...
        system.cpu0.lsq0.LLIssued                          42  # LL issued
        system.cpu1.lsq0.LLIssued                          37  # LL issued

    `scalar_stats` is a dict of {column_name: stat_keyword} for stats that
    appear once in the file (e.g. simTicks). The first matching line is used.

    `per_core_stats` is a dict of {column_name: stat_keyword} for stats that
    appear once per core as "system.cpu<i>.lsq0.<stat_keyword>". Every core's
    value is found and summed into a single total.
    """
    results = {name: None for name in list(scalar_stats) + list(per_core_stats)}

    try:
        with open(stats_path, "r", errors="ignore") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return results

    # --- scalar stats: take the first match ---
    for name, keyword in scalar_stats.items():
        pattern = re.compile(
            r"^(?:\S*\.)?" + re.escape(keyword) + r"\s+" + _NUMBER_RE,
            re.MULTILINE,
        )
        for line in lines:
            match = pattern.match(line.strip())
            if match:
                results[name] = _to_number(match.group(1))
                break

    # --- per-core stats: sum across every system.cpu<i>.lsq0.<keyword> ---
    for name, keyword in per_core_stats.items():
        if (cpu_type == "minor"):
            patternString =  r"^system\.cpu\d+\.lsq\." + re.escape(keyword) + r"\s+" + _NUMBER_RE
        else:
            patternString =  r"^system\.cpu\d+\.lsq0\." + re.escape(keyword) + r"\s+" + _NUMBER_RE

        pattern = re.compile(patternString)
        total = None
        for line in lines:
            match = pattern.match(line.strip())
            if match:
                value = _to_number(match.group(1))
                total = value if total is None else total + value
        results[name] = total

    return results


def collect_results(root_dir):
    """
    Walk root_dir looking for directories that contain both simout.txt and
    stats.txt, extract the relevant info from each, and return a pandas
    DataFrame indexed by directory path.
    """
    records = {}

    for dirpath, _dirnames, filenames in os.walk(root_dir):
        SFUCdirNameRE = r"SF-uc-bb-([0-9]+)-(minor|o3)-(one|two)-level-(tbe|cbe)-([0-9]+)-num-cpus-([0-9]+)"
        SFCdirNameRE = r"SF-(cnr|cr)-bb-([0-9]+)-(eb|rb)-([0-9]+)-(minor|o3)-(one|two)-level-(tbe|cbe)-([0-9]+)-num-cpus-([0-9]+)"
        NOSFUCdirNameRE = r"NOSF-uc-bb-([0-9]+)-(minor|o3)-(one|two)-level-num-cpus-([0-9]+)"
        NOSFCdirNameRE = r"NOSF-(cnr|cr)-bb-([0-9]+)-(eb|rb)-([0-9]+)-(minor|o3)-(one|two)-level-num-cpus-([0-9]+)"

        if "simout.txt" in filenames and "stats.txt" in filenames:
            simout_path = os.path.join(dirpath, "simout.txt")
            stats_path = os.path.join(dirpath, "stats.txt")

            success = check_simout(simout_path)
            row = {"success": success}

            # Use the directory path (relative to root_dir) as the key.
            key = os.path.relpath(dirpath, root_dir)
            #print (f"Looking at {key}")
            matchSFUC = re.match(SFUCdirNameRE, key) 
            matchSFC = re.match(SFCdirNameRE, key) 
            matchNoSFUC = re.match(NOSFUCdirNameRE, key)
            matchNoSFC = re.match(NOSFCdirNameRE, key)
            cpu_type = "o3"
            if (matchSFUC):
                row.update({"mode": "SF", \
                            "lrsc-type": "uc", \
                            "blobs-between": matchSFUC.group(1), \
                            "condition-type": None, \
                            "blobs-exit-retry": None, \
                            "cpu-type": matchSFUC.group(2), \
                            "cache-levels": matchSFUC.group(3), \
                            "ee-type": matchSFUC.group(4), \
                            "ee-config": matchSFUC.group(5), \
                            "num-cpus": matchSFUC.group(6)})
                if (matchSFUC.group(2) == "minor"):
                    cpu_type = "minor"
            if (matchSFC):
                row.update({"mode": "SF", \
                            "lrsc-type": matchSFC.group(1),\
                            "blobs-between": matchSFC.group(2), \
                            "condition-type": matchSFC.group(3), \
                            "blobs-exit-retry": matchSFC.group(4), \
                            "cpu-type": matchSFC.group(5), \
                            "cache-levels": matchSFC.group(6), \
                            "ee-type": matchSFC.group(7), \
                            "ee-config": matchSFC.group(8), \
                            "num-cpus": matchSFC.group(9)})
                if (matchSFC.group(5) == "minor"):
                    cpu_type = "minor"
            if (matchNoSFUC):
                row.update({"mode": "NOSF", \
                            "lrsc-type": "uc", \
                            "blobs-between": matchNoSFUC.group(1), \
                            "condition-type": None, \
                            "blobs-exit-retry": None, \
                            "cpu-type": matchNoSFUC.group(2), \
                            "cache-levels": matchNoSFUC.group(3), \
                            "ee-type": None, \
                            "ee-config": None, \
                            "num-cpus": matchNoSFUC.group(4)})
                if (matchNoSFUC.group(2) == "minor"):
                    cpu_type = "minor"
            if (matchNoSFC):
                row.update({"mode": "NOSF", \
                            "lrsc-type": matchNoSFC.group(1),\
                            "blobs-between": matchNoSFC.group(2), \
                            "condition-type": matchNoSFC.group(3), \
                            "blobs-exit-retry": matchNoSFC.group(4), \
                            "cpu-type": matchNoSFC.group(5), \
                            "cache-levels": matchNoSFC.group(6), \
                            "ee-type": None, \
                            "ee-config": None, \
                            "num-cpus": matchNoSFC.group(7)})
                if (matchNoSFC.group(5) == "minor"):
                    cpu_type = "minor"

            stats = parse_stats(stats_path, SCALAR_STATS, PER_CORE_STATS, cpu_type)
            row.update(stats)

            records[key] = row

    df = pd.DataFrame.from_dict(records, orient="index")
    df.index.name = "directory"

    # Keep a nice, predictable column order if the DataFrame isn't empty
    if not df.empty:
        ordered_cols = ["success"] + list(SCALAR_STATS.keys()) + list(PER_CORE_STATS.keys()) + list(DIRECTORY_NAME_STATS.keys())
        df = df[ordered_cols]

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Traverse directories and extract gem5 simout/stats info into a DataFrame."
    )
    parser.add_argument("root_dir", help="Root directory to search recursively.")
    parser.add_argument(
        "-o", "--output", help="Optional path to save results as a CSV file.", default=None
    )
    args = parser.parse_args()

    df = collect_results(args.root_dir)

    if df.empty:
        print("No directories containing both simout.txt and stats.txt were found.")
    else:
        # Print full table without truncation
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(df)

    if args.output:
        df.to_csv(args.output)
        print(f"\nSaved results to {args.output}")


if __name__ == "__main__":
    main()

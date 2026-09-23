#!/usr/bin/python3
import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def generate_multi_index_heatmap(
    csv_file: str, x_param: str = "cbe", output_file: str = "heatmap_multiindex.png"
):
    # Load dataset
    df = pd.read_csv(csv_file)

    # Clean/format rb values (replace NaN with '-' so it renders cleanly in labels)
    df["rb_str"] = df["rb"].fillna("-")

    # Filter non-null entries for the specified target parameter sweep (e.g., 'cbe' or 'tbe')
    df_filtered = df[df[x_param].notna()].copy()

    # Create pivot table with a multi-index y-axis [bb, rb, eb]
    pivot_df = df_filtered.pivot(
        #index=["bb", "rb_str", "eb"], columns=x_param, values="normalized_simTicks"
        index=["bb", "rb_str"], columns=x_param, values="normalized_simTicks"
    )

    # Format multi-index tuple labels for the y-axis (bb, rb, eb)
    #pivot_df.index = [f"({bb}, {rb}, {eb})" for bb, rb, eb in pivot_df.index]
    pivot_df.index = [f"<{bb}, {rb}>" for bb, rb in pivot_df.index]

    # Configure colormap reserving black for missing/unsimulated data points
    cmap = plt.cm.YlGnBu.copy()
    cmap.set_bad(color="black")

    # Plot figure
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_facecolor("pink")  # Ensures empty grid cells render black

    sns.heatmap(
        pivot_df,
        cmap=cmap,
        ax=ax,
        cbar_kws={"label": "Normalized runtime"},
        linewidths=0.2,
        linecolor="#222222",
    )

    ax.figure.axes[-1].yaxis.label.set_size(20)
    ax.figure.axes[-1].tick_params(labelsize=15)
    ax.tick_params(labelsize=15)


    ax.set_title(
        #f"Success/Fail timer configurations",
        f"",
        #runtime for synthetic workloads using {x_param.upper()} configuration",
        fontsize=20,
        fontweight="bold",
        pad=12,
    )
    #ax.set_ylabel("(bb, rb, eb)", fontsize=11, fontweight="bold")
    ax.set_ylabel("<i,j>", fontsize=20, fontweight="bold")
    ax.set_xlabel("Timer value", fontsize=20, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close()


# Run for CBE and TBE sweeps


def main():
    parser = argparse.ArgumentParser(
            description="Heatmap visualizer"
            )

    parser.add_argument("csv_path", help="Path to csv to generate heatmap")
    args = parser.parse_args()

    #generate_multi_index_heatmap(args.csv_path, x_param="cbe", output_file=str(args.csv_path)+"_cbe.png")
    generate_multi_index_heatmap(args.csv_path, x_param="tbe", output_file=str(args.csv_path)+"_tbe.png")


if __name__ == "__main__":
    main()


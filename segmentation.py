"""
Customer Segmentation using RFM analysis + K-Means clustering
=============================================================
Pipeline:  load -> clean -> RFM features -> log + standard scaling
           -> choose k (elbow + silhouette) -> K-Means (k=3)
           -> name the 3 groups automatically -> graphs -> ONE csv

Run:
    python segmentation.py                         # uses data/online_retail_sample.csv
    python segmentation.py --input OnlineRetail.xlsx   # use the real UCI dataset
    python segmentation.py --no-show               # save graphs only (no pop-up windows)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

# Import modular pipeline functions
from ml_pipeline import (
    load_data as pipe_load,
    clean_data as pipe_clean,
    build_rfm as pipe_build_rfm,
    scale_rfm as pipe_scale,
    evaluate_k as pipe_evaluate_k,
    name_clusters as pipe_name_clusters,
    DEFAULT_N_CLUSTERS,
    DEFAULT_RANDOM_STATE,
    DEFAULT_MAX_QTY,
    DEFAULT_MAX_PRICE
)

# ---------------------------------------------------------------- settings
BASE = Path(__file__).parent
DEFAULT_INPUT = BASE / "data" / "online_retail_sample.csv"
OUT_DIR = BASE / "outputs"
OUT_CSV = OUT_DIR / "customer_segments.csv"
N_CLUSTERS = DEFAULT_N_CLUSTERS
RANDOM_STATE = DEFAULT_RANDOM_STATE
MAX_QTY, MAX_PRICE = DEFAULT_MAX_QTY, DEFAULT_MAX_PRICE          # outlier limits (same as reference project)
COLORS = {"VIP": "#2E9E5B", "Regular": "#3B7DD8", "Rare": "#E67300"}


def parse_args():
    p = argparse.ArgumentParser(description="RFM + K-Means customer segmentation")
    p.add_argument("--input", default=str(DEFAULT_INPUT), help="CSV or XLSX transactions file")
    p.add_argument("--no-show", action="store_true", help="save graphs without opening windows")
    return p.parse_args()


args = parse_args()
import matplotlib
if args.no_show:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")
OUT_DIR.mkdir(exist_ok=True)


def banner(text):
    print("\n" + "=" * 70 + f"\n{text}\n" + "=" * 70)


# ---------------------------------------------------------------- 1. load
def load(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"Input file not found: {path}\n"
                 "Run `python generate_sample_data.py` first, or pass --input <file>.")
    return pipe_load(path)


# ---------------------------------------------------------------- 2. clean
def clean(df):
    cleaned_df, audit_steps = pipe_clean(df, max_qty=MAX_QTY, max_price=MAX_PRICE, remove_cancellations=True)
    steps = [(s["step"], s["count"]) for s in audit_steps]
    return cleaned_df, steps


# ---------------------------------------------------------------- 3. RFM
def build_rfm(df):
    return pipe_build_rfm(df)


# ---------------------------------------------------------------- 4. scale
def scale(rfm):
    scaled_df, _ = pipe_scale(rfm)
    return scaled_df


# ---------------------------------------------------------------- 5. choose k
def evaluate_k(X, k_max=10):
    return pipe_evaluate_k(X, k_min=2, k_max=k_max, random_state=RANDOM_STATE)


# ---------------------------------------------------------------- 6. name groups
def name_clusters(rfm, labels):
    """Rank clusters by a value score so names never depend on K-Means' random numbering."""
    mapping, _ = pipe_name_clusters(rfm, labels, n_clusters=N_CLUSTERS)
    return mapping


# ---------------------------------------------------------------- main
def main():
    banner("1. LOAD DATA")
    raw = load(args.input)
    print(f"File: {args.input}\nRows: {len(raw):,}   Columns: {list(raw.columns)}")

    banner("2. CLEAN DATA")
    df, steps = clean(raw)
    for name, n in steps:
        print(f"  {name:<22}{n:>10,}")
    print(f"  -> kept {len(df):,} of {len(raw):,} rows ({len(df)/len(raw):.0%}), "
          f"{df['CustomerID'].nunique():,} customers")

    banner("3. RFM FEATURES (one row per customer)")
    rfm = build_rfm(df)
    print(rfm.describe().round(1))

    banner("4. SCALE (log + standardise)")
    X = scale(rfm)
    print("Scaled means ~0, std ~1:\n", X.agg(["mean", "std"]).round(3))

    banner("5. CHOOSE NUMBER OF GROUPS")
    ks, wcss, sil = evaluate_k(X)
    for k, w, s in zip(ks, wcss, sil):
        print(f"  k={k:<2} WCSS={w:>9.1f}  silhouette={s:.3f}{'   <-- used' if k == N_CLUSTERS else ''}")

    banner(f"6. K-MEANS WITH k={N_CLUSTERS}")
    model = KMeans(n_clusters=N_CLUSTERS, init="k-means++", n_init=10, random_state=RANDOM_STATE).fit(X)
    names = name_clusters(rfm, model.labels_)
    rfm["Cluster"] = model.labels_
    rfm["Segment"] = rfm["Cluster"].map(names)
    final_sil = silhouette_score(X, model.labels_, sample_size=min(5000, len(X)), random_state=RANDOM_STATE)
    print(f"Silhouette score for k={N_CLUSTERS}: {final_sil:.3f}  (closer to 1 = better separated)")

    order = ["VIP", "Regular", "Rare"]
    summary = (rfm.groupby("Segment").agg(
        Customers=("Recency", "size"), Avg_Recency=("Recency", "mean"),
        Avg_Frequency=("Frequency", "mean"), Avg_Spend=("Monetary", "mean"),
        Total_Spend=("Monetary", "sum")).loc[order])
    summary["% Customers"] = summary["Customers"] / summary["Customers"].sum() * 100
    summary["% Revenue"] = summary["Total_Spend"] / summary["Total_Spend"].sum() * 100
    print("\nSEGMENT SUMMARY"); print(summary.round(1).to_string())

    # ---------------- ONE csv: every customer and the group he/she belongs to
    rfm.reset_index()[["CustomerID", "Recency", "Frequency", "Monetary", "Cluster", "Segment"]] \
       .sort_values(["Segment", "Monetary"], key=lambda c: c.map({n: i for i, n in enumerate(order)}) if c.name == "Segment" else -c) \
       .to_csv(OUT_CSV, index=False)
    print(f"\nSaved segmentation file -> {OUT_CSV}")

    banner("7. GRAPHS")
    plot_all(rfm, summary, ks, wcss, sil, order)

    banner("DONE")
    for seg in order:
        s = summary.loc[seg]
        print(f"  {seg:<8} {int(s.Customers):>5} customers  ({s['% Customers']:.1f}% of customers, {s['% Revenue']:.1f}% of revenue)")
    print(f"\nFiles in {OUT_DIR}/ :  customer_segments.csv  +  graph PNGs")
    if not args.no_show:
        plt.show()


# ---------------------------------------------------------------- plots
def save(fig, name):
    fig.savefig(OUT_DIR / name, dpi=140, bbox_inches="tight")
    print(f"  saved {name}")


def plot_all(rfm, summary, ks, wcss, sil, order):
    # 1 -- choosing k
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].plot(ks, wcss, "o--", color="#E67300", lw=2)
    ax[0].axvline(N_CLUSTERS, color="grey", ls=":"); ax[0].set(title="Elbow method", xlabel="Number of clusters (k)", ylabel="WCSS (inertia)")
    ax[1].plot(ks, sil, "o--", color="#3B7DD8", lw=2)
    ax[1].axvline(N_CLUSTERS, color="grey", ls=":"); ax[1].set(title="Silhouette score", xlabel="Number of clusters (k)", ylabel="Score")
    fig.suptitle("Choosing the number of groups", fontweight="bold"); fig.tight_layout(); save(fig, "1_choose_k.png")

    # 2 -- group sizes vs revenue
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    cols = [COLORS[s] for s in order]
    ax[0].pie(summary["Customers"], labels=order, colors=cols, autopct="%1.1f%%", startangle=90, wedgeprops=dict(edgecolor="white"))
    ax[0].set_title("Share of customers")
    ax[1].pie(summary["Total_Spend"], labels=order, colors=cols, autopct="%1.1f%%", startangle=90, wedgeprops=dict(edgecolor="white"))
    ax[1].set_title("Share of revenue")
    fig.suptitle("Who the customers are vs. who brings the money", fontweight="bold"); fig.tight_layout(); save(fig, "2_segment_share.png")

    # 3 -- scatter with centroids (centroids computed from data, not typed in)
    cent = rfm.groupby("Segment")[["Recency", "Monetary"]].mean().loc[order]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    sns.scatterplot(data=rfm, x="Recency", y="Monetary", hue="Segment", hue_order=order, palette=COLORS,
                    alpha=.55, s=35, edgecolor=None, ax=ax)
    ax.scatter(cent["Recency"], cent["Monetary"], s=380, c="gold", edgecolor="black", lw=2, marker="*", label="Centroid", zorder=5)
    ax.set_yscale("log"); ax.set(title="Customer groups: Recency vs Total Spend (log scale)",
                                 xlabel="Recency (days since last purchase)", ylabel="Total spend")
    ax.legend(title="Group"); fig.tight_layout(); save(fig, "3_scatter_segments.png")

    # 4 -- boxplots of R, F, M per group
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    for a, col, lab, logy in zip(ax, ["Recency", "Frequency", "Monetary"],
                                 ["Days since last order", "Number of orders", "Total spend"], [False, True, True]):
        sns.boxplot(data=rfm, x="Segment", y=col, order=order, hue="Segment", palette=COLORS, legend=False, ax=a)
        if logy: a.set_yscale("log")
        a.set(title=f"{col}", xlabel="", ylabel=lab)
    fig.suptitle("Recency, Frequency and Monetary by group", fontweight="bold"); fig.tight_layout(); save(fig, "4_rfm_boxplots.png")

    # 5 -- average profile heatmap
    prof = rfm.groupby("Segment")[["Recency", "Frequency", "Monetary"]].mean().loc[order]
    z = (prof - prof.mean()) / prof.std(ddof=0)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    sns.heatmap(z, annot=prof.round(1), fmt="", cmap="RdYlGn", center=0, cbar_kws={"label": "relative level"}, ax=ax)
    ax.set(title="Average profile of each group", ylabel="")
    fig.tight_layout(); save(fig, "5_profile_heatmap.png")

    # 6 -- 3D view
    fig = plt.figure(figsize=(9, 7)); ax = fig.add_subplot(111, projection="3d")
    for s in order:
        d = rfm[rfm["Segment"] == s]
        ax.scatter(d["Recency"], np.log10(d["Frequency"]), np.log10(d["Monetary"]), c=COLORS[s], label=s, s=14, alpha=.6)
    ax.set(xlabel="Recency (days)", ylabel="log10 Frequency", zlabel="log10 Monetary", title="All three RFM dimensions together")
    ax.legend(); fig.tight_layout(); save(fig, "6_3d_view.png")


if __name__ == "__main__":
    main()

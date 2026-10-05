from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TABLES, OUT = ROOT / "reports" / "tables", ROOT / "reports"

BLUE, ORANGE, INK, MUTED, GRID, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "axes.titlelocation": "left", "axes.titlesize": 11, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True,
})


def pct(ax, axis="x"):
    fmt = matplotlib.ticker.PercentFormatter(1, decimals=0)
    (ax.xaxis if axis == "x" else ax.yaxis).set_major_formatter(fmt)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)


def funnel():
    f = pd.read_csv(TABLES / "funnel.csv")
    fig, ax = plt.subplots(figsize=(6, 3.6))
    labels = [f"Order {k}" for k in f.order_k]
    ax.bar(labels, f.share_of_users, color=BLUE, width=0.55)
    for i, s in enumerate(f.share_of_users):
        ax.text(i, s + 0.015, f"{s:.1%}", ha="center", color=INK)
    ax.set(ylim=(0, 1.12), title="Share of users who reach order k")
    ax.grid(axis="x", visible=False)
    pct(ax, "y")
    ax.text(0.99, -0.2, "Every user has at least 4 orders, so orders 1-3 are 100% by construction.",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    save(fig, "funnel.png")


def retention_curve():
    c = pd.read_csv(TABLES / "return_curve.csv")
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(c.day, c.share_returned_by_day, color=BLUE, lw=2)
    for d in (7, 14):
        v = c.loc[c.day == d, "share_returned_by_day"].item()
        ax.plot(d, v, "o", color=BLUE, ms=7, mec=SURFACE, mew=2)
        ax.annotate(f"day {d}: {v:.1%}", (d, v), xytext=(8, -14), textcoords="offset points", color=INK)
    ax.set(xlabel="Days since first order", title="Share of users whose second order came by day d",
           xlim=(0, 29), ylim=(0, 0.85))
    pct(ax, "y")
    ax.text(0.99, 0.04, "Gap of 30 days is a cap ('30 or more'), so the curve stops at day 29.",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    save(fig, "return_curve.png")


def retention_segments():
    r = pd.read_csv(TABLES / "retention_by_segment.csv")
    overall = r[r.segment_type == "all"].iloc[0]
    basket = r[r.segment_type == "first_basket_size"].copy()
    basket["order"] = basket.segment.str.extract(r"(\d+)").astype(int)
    basket = basket.sort_values("order")
    dept = r[(r.segment_type == "first_basket_top_department") & r.meets_min_users].sort_values("retained_14d")

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"width_ratios": [1, 1.4]})
    x = range(len(basket))
    a.bar([i - 0.19 for i in x], basket.retained_7d, 0.36, color=BLUE, label="within 7 days")
    a.bar([i + 0.19 for i in x], basket.retained_14d, 0.36, color=ORANGE, label="within 14 days")
    a.set_xticks(list(x), basket.segment)
    a.set(title="By size of first basket", ylim=(0, 0.7))
    a.grid(axis="x", visible=False)
    a.legend(frameon=False, loc="upper left")
    pct(a, "y")
    b.barh(dept.segment, dept.retained_14d, color=BLUE, height=0.65)
    b.axvline(overall.retained_14d, color=MUTED, lw=1, ls="--")
    b.text(overall.retained_14d + 0.003, -0.9, f"all users {overall.retained_14d:.1%}", color=MUTED, fontsize=8)
    b.set(title="14-day return by top department of first basket\n(departments with 1,000+ users)",
          xlim=(0.4, 0.62), xticks=[0.4, 0.45, 0.5, 0.55, 0.6])
    b.grid(axis="y", visible=False)
    pct(b)
    save(fig, "retention_by_segment.png")


def activity_curve():
    c = pd.read_csv(TABLES / "activity_curve.csv")
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.plot(c.day, c.share_still_ordering, color=BLUE, lw=2, marker="o", ms=5, mec=SURFACE, mew=1.5)
    ax.set(xlabel="Days since first order", ylim=(0, 1.05),
           title="Share of users with an order on or after day d")
    ax.set_xticks(c.day[::2])
    pct(ax, "y")
    ax.text(0.99, 0.95, "Day offsets are lower bounds because gaps are capped at 30.",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    save(fig, "activity_curve.png")


def reorder_departments():
    d = pd.read_csv(TABLES / "reorder_by_department.csv")
    d = d[d.meets_min_support].sort_values("reorder_rate")
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.barh(d.department, d.reorder_rate, color=BLUE, height=0.65)
    for y, v in enumerate(d.reorder_rate):
        ax.text(v + 0.008, y, f"{v:.1%}", va="center", fontsize=8, color=INK)
    ax.set(xlim=(0, 0.82), title="Reorder rate by department (orders after the first)")
    ax.grid(axis="y", visible=False)
    pct(ax)
    save(fig, "reorder_by_department.png")


def affinity():
    by_count = pd.read_csv(TABLES / "affinity_top_by_count.csv").head(10)
    by_lift = pd.read_csv(TABLES / "affinity_top_by_lift.csv").head(10)

    def label(r):
        short = lambda s: s if len(s) <= 55 else s[:54] + "…"
        return f"{short(r.product_a_name)}\n+ {short(r.product_b_name)}"

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharex=True)
    for ax, df, title in zip(axes, (by_count, by_lift), ("Ten most frequent pairs", "Ten highest-lift pairs")):
        df = df.iloc[::-1]
        ax.barh([label(r) for r in df.itertuples()], df.lift, color=BLUE, height=0.65)
        for y, (v, n) in enumerate(zip(df.lift, df.pair_orders)):
            ax.text(v + 0.5, y, f"lift {v:.1f}, {n:,} baskets", va="center", fontsize=7.5)
        ax.set(title=title, xlabel="Lift (1 = no association beyond popularity)")
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="y", visible=False)
    axes[0].set_xlim(0, 75)
    save(fig, "affinity_count_vs_lift.png")


if __name__ == "__main__":
    for fn in (funnel, retention_curve, retention_segments, activity_curve, reorder_departments, affinity):
        fn()

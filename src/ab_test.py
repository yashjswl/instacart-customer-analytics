"""Simulated A/B test. The data has no experiment, see docs/ab_test_design.md.

Control outcomes are real users' outcomes, the treatment effect is injected and known.
"""
import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parent.parent

ALPHA = 0.05
POWER = 0.80
MDE = 0.02
GUARDRAIL_MARGIN = 0.5
SRM_ALPHA = 0.001
SEED = 42
N_SIMS = 2000


def sample_size_per_arm(p0, mde, alpha=ALPHA, power=POWER):
    return int(np.ceil(_n_exact(p0, mde, alpha, power)))


def _n_exact(p0, mde, alpha, power):
    p1 = p0 + mde
    pbar = (p0 + p1) / 2
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return (za * np.sqrt(2 * pbar * (1 - pbar)) + zb * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / mde**2


def mde_for_n(p0, n_per_arm, alpha=ALPHA, power=POWER):
    return optimize.brentq(lambda d: _n_exact(p0, d, alpha, power) - n_per_arm, 1e-5, 1 - p0 - 1e-5)


def two_prop_ztest(x_t, n_t, x_c, n_c):
    """Pooled two-sided z-test for the difference in proportions (treatment - control)."""
    p_pool = (x_t + x_c) / (n_t + n_c)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    z = (x_t / n_t - x_c / n_c) / se
    return z, 2 * stats.norm.sf(abs(z))


def diff_ci(x_t, n_t, x_c, n_c, alpha=ALPHA):
    pt, pc = x_t / n_t, x_c / n_c
    se = np.sqrt(pt * (1 - pt) / n_t + pc * (1 - pc) / n_c)
    z = stats.norm.ppf(1 - alpha / 2)
    return pt - pc - z * se, pt - pc + z * se


def relative_lift_ci(x_t, n_t, x_c, n_c, alpha=ALPHA):
    """Lift = risk ratio - 1, interval from the delta method on log(risk ratio)."""
    log_rr = np.log((x_t / n_t) / (x_c / n_c))
    se = np.sqrt(1 / x_t - 1 / n_t + 1 / x_c - 1 / n_c)
    z = stats.norm.ppf(1 - alpha / 2)
    return np.exp(log_rr) - 1, np.exp(log_rr - z * se) - 1, np.exp(log_rr + z * se) - 1


def srm_pvalue(n_c, n_t, expected_treatment_share=0.5):
    total = n_c + n_t
    expected = [total * (1 - expected_treatment_share), total * expected_treatment_share]
    return stats.chisquare([n_c, n_t], expected).pvalue


def guardrail_lower_bound(g_t, g_c, alpha=ALPHA):
    """One-sided lower confidence bound for mean(g_t) - mean(g_c), Welch."""
    v_t, v_c = np.var(g_t, ddof=1) / len(g_t), np.var(g_c, ddof=1) / len(g_c)
    se = np.sqrt(v_t + v_c)
    df = (v_t + v_c) ** 2 / (v_t**2 / (len(g_t) - 1) + v_c**2 / (len(g_c) - 1))
    diff = np.mean(g_t) - np.mean(g_c)
    return diff, diff - stats.t.ppf(1 - alpha, df) * se


def analyze(arm, y, g):
    """arm: 1 = treatment. y: converted 0/1. g: guardrail value, NaN when the user did not convert."""
    t, c = arm == 1, arm == 0
    n_t, n_c, x_t, x_c = t.sum(), c.sum(), y[t].sum(), y[c].sum()
    z, p = two_prop_ztest(x_t, n_t, x_c, n_c)
    lo, hi = diff_ci(x_t, n_t, x_c, n_c)
    rel, rel_lo, rel_hi = relative_lift_ci(x_t, n_t, x_c, n_c)
    g_diff, g_lower = guardrail_lower_bound(g[t & (y == 1)], g[c & (y == 1)])
    srm_p = srm_pvalue(n_c, n_t)
    srm_flag = srm_p < SRM_ALPHA
    primary_win = (p < ALPHA) and (x_t / n_t > x_c / n_c)
    guardrail_ok = g_lower > -GUARDRAIL_MARGIN
    return {
        "n_control": n_c, "n_treatment": n_t, "srm_p": srm_p, "srm_flag": srm_flag,
        "rate_control": x_c / n_c, "rate_treatment": x_t / n_t,
        "abs_lift": x_t / n_t - x_c / n_c, "abs_lift_ci_low": lo, "abs_lift_ci_high": hi,
        "rel_lift": rel, "rel_lift_ci_low": rel_lo, "rel_lift_ci_high": rel_hi,
        "z": z, "p_value": p,
        "guardrail_diff": g_diff, "guardrail_lower_bound": g_lower, "guardrail_ok": guardrail_ok,
        "ship": bool(not srm_flag and primary_win and guardrail_ok),
    }


class Pool:
    """Real users: control outcome and second-order basket size."""

    def __init__(self, df):
        self.y = df["returned_14d"].to_numpy()
        self.g = df["second_basket_size"].to_numpy(dtype=float)
        self.p0 = self.y.mean()
        self.returner_sizes = self.g[~np.isnan(self.g)]


def simulate_experiment(rng, pool, n_per_arm, effect=0.0, harm=0.0, srm_drop=0.0):
    """effect: absolute lift injected on the primary metric. harm: items removed from treated
    users' second orders. srm_drop: share of treated users lost after assignment (a pipeline bug)."""
    idx = rng.choice(len(pool.y), 2 * n_per_arm, replace=False)
    arm = (rng.random(len(idx)) < 0.5).astype(int)
    y, g = pool.y[idx].copy(), pool.g[idx].copy()
    if effect:
        flip = (arm == 1) & (y == 0) & (rng.random(len(idx)) < effect / (1 - pool.p0))
        y[flip] = 1
        g[flip] = rng.choice(pool.returner_sizes, flip.sum())
    if harm:
        g[arm == 1] -= harm
    if srm_drop:
        keep = ~((arm == 1) & (rng.random(len(idx)) < srm_drop))
        arm, y, g = arm[keep], y[keep], g[keep]
    return arm, y, g


def run_many(pool, n_per_arm, seed_seq, n_sims=N_SIMS, **kwargs):
    rng = np.random.default_rng(seed_seq)
    return pd.DataFrame([analyze(*simulate_experiment(rng, pool, n_per_arm, **kwargs)) for _ in range(n_sims)])


def summarize(name, res, effect, harm, srm_drop):
    def rate(col):
        return res[col].mean()
    se = lambda p: np.sqrt(p * (1 - p) / len(res))
    covered = ((res.abs_lift_ci_low <= effect) & (effect <= res.abs_lift_ci_high)).mean()
    return {
        "scenario": name, "n_sims": len(res), "true_effect": effect, "guardrail_harm_items": harm,
        "srm_drop": srm_drop,
        "primary_significant_rate": (res.p_value < ALPHA).mean(),
        "primary_significant_mc_se": se((res.p_value < ALPHA).mean()),
        "mean_abs_lift_estimate": res.abs_lift.mean(),
        "abs_lift_ci_coverage": covered,
        "guardrail_fail_rate": 1 - rate("guardrail_ok"),
        "srm_flag_rate": rate("srm_flag"),
        "ship_rate": rate("ship"),
    }


def main(db_path, out_root):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    con = duckdb.connect(str(db_path), read_only=True)
    pool = Pool(con.execute("SELECT * FROM ab_users ORDER BY user_id").df())
    con.close()
    tables, figures = Path(out_root) / "reports" / "tables", Path(out_root) / "reports"
    tables.mkdir(parents=True, exist_ok=True)

    n = sample_size_per_arm(pool.p0, MDE)
    plan = pd.DataFrame([{
        "baseline_rate": pool.p0, "alpha": ALPHA, "power": POWER, "mde_abs": MDE,
        "n_per_arm": n, "n_total": 2 * n, "available_users": len(pool.y),
        "mde_if_all_users_used": mde_for_n(pool.p0, len(pool.y) // 2),
    }])
    plan.to_csv(tables / "ab_power_plan.csv", index=False)
    sizes = pd.DataFrame({"mde_abs": [0.005, 0.01, 0.02, 0.03, 0.05]})
    sizes["n_per_arm"] = [sample_size_per_arm(pool.p0, d) for d in sizes.mde_abs]
    sizes.to_csv(tables / "ab_sample_sizes.csv", index=False)

    seeds = np.random.SeedSequence(SEED).spawn(6)
    demo_rng = np.random.default_rng(seeds[0])
    demo = analyze(*simulate_experiment(demo_rng, pool, n, effect=MDE))
    pd.DataFrame([{"true_effect": MDE, **demo}]).to_csv(tables / "ab_demo_run.csv", index=False)

    scenarios = [
        ("effect_at_mde", dict(effect=MDE), seeds[1]),
        ("aa_no_effect", dict(), seeds[2]),
        ("effect_with_guardrail_harm", dict(effect=MDE, harm=1.0), seeds[3]),
        ("effect_with_srm_bug", dict(effect=MDE, srm_drop=0.05), seeds[4]),
    ]
    rows, results = [], {}
    for name, kw, seed in scenarios:
        res = run_many(pool, n, seed, **kw)
        results[name] = res
        rows.append(summarize(name, res, kw.get("effect", 0.0), kw.get("harm", 0.0), kw.get("srm_drop", 0.0)))
    pd.DataFrame(rows).to_csv(tables / "ab_scenarios.csv", index=False)

    tag = "SIMULATED experiment, real baseline"
    fig, ax = plt.subplots(figsize=(6, 4))
    grid = np.linspace(0.005, 0.05, 60)
    ax.plot(grid * 100, [sample_size_per_arm(pool.p0, d) for d in grid])
    ax.axvline(MDE * 100, ls="--", c="grey")
    ax.set(xlabel="Minimum detectable effect (percentage points)", ylabel="Users per arm",
           title=f"Sample size for 80% power, alpha 0.05\n({tag}, baseline {pool.p0:.3f})")
    fig.tight_layout(); fig.savefig(figures / "ab_sample_size.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(results["aa_no_effect"].p_value, bins=20, range=(0, 1))
    axes[0].set(xlabel="p-value", ylabel="Simulations",
                title=f"A/A p-values, should be flat\n(SIMULATED, {N_SIMS} runs)")
    axes[1].hist(results["effect_at_mde"].abs_lift * 100, bins=30)
    axes[1].axvline(MDE * 100, c="k", ls="--", label="true effect")
    axes[1].set(xlabel="Estimated lift (percentage points)", title=f"Estimated lift, true effect 2 pp\n(SIMULATED, {N_SIMS} runs)")
    axes[1].legend()
    fig.tight_layout(); fig.savefig(figures / "ab_simulation_checks.png", dpi=150); plt.close(fig)
    print(plan.T.to_string(header=False))
    print(pd.DataFrame(rows).T.to_string(header=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=ROOT / "data" / "instacart.duckdb")
    args = ap.parse_args()
    main(args.db, ROOT)

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (confint_proportions_2indep, proportion_effectsize,
                                          proportions_ztest)

from src import ab_test as ab


def test_ztest_textbook_example():
    # 100/200 vs 80/200: pooled p = 0.45, se = sqrt(0.45 * 0.55 * 2/200), z = 0.1 / se = 2.0101
    z, p = ab.two_prop_ztest(100, 200, 80, 200)
    assert z == pytest.approx(0.1 / np.sqrt(0.45 * 0.55 * 0.01), rel=1e-12)
    assert z == pytest.approx(2.0101, abs=1e-4)
    assert p == pytest.approx(0.0444, abs=1e-4)


def test_ztest_matches_statsmodels():
    z, p = ab.two_prop_ztest(5480, 9632, 5300, 9632)
    z_sm, p_sm = proportions_ztest([5480, 5300], [9632, 9632])
    assert z == pytest.approx(z_sm) and p == pytest.approx(p_sm)


def test_diff_and_relative_ci_match_statsmodels():
    x_t, n_t, x_c, n_c = 5480, 9632, 5300, 9632
    lo, hi = ab.diff_ci(x_t, n_t, x_c, n_c)
    sm = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="wald")
    assert (lo, hi) == pytest.approx(sm)
    rel, rel_lo, rel_hi = ab.relative_lift_ci(x_t, n_t, x_c, n_c)
    sm_ratio = confint_proportions_2indep(x_t, n_t, x_c, n_c, compare="ratio", method="log")
    assert rel == pytest.approx((x_t / n_t) / (x_c / n_c) - 1)
    assert (rel_lo + 1, rel_hi + 1) == pytest.approx(sm_ratio)


def test_sample_size_textbook_and_statsmodels():
    # 50% vs 60%, alpha 0.05, power 0.8: the usual textbook figure is about 388 per group
    assert ab.sample_size_per_arm(0.5, 0.1) == pytest.approx(388, abs=1)
    for p0, d in [(0.557, 0.02), (0.3, 0.05), (0.1, 0.01)]:
        sm = NormalIndPower().solve_power(proportion_effectsize(p0 + d, p0), alpha=0.05, power=0.8)
        assert ab.sample_size_per_arm(p0, d) == pytest.approx(sm, rel=0.01)


def test_mde_inverts_sample_size():
    n = ab.sample_size_per_arm(0.55, 0.02)
    assert ab.mde_for_n(0.55, n) == pytest.approx(0.02, abs=1e-4)


def test_srm():
    assert ab.srm_pvalue(5000, 5000) == pytest.approx(1.0)
    assert ab.srm_pvalue(4500, 5500) < 1e-10
    assert ab.srm_pvalue(5050, 4950) > ab.SRM_ALPHA


def test_guardrail_matches_scipy_welch():
    rng = np.random.default_rng(1)
    g_t, g_c = rng.normal(9.5, 6, 400), rng.normal(10, 7, 500)
    diff, lower = ab.guardrail_lower_bound(g_t, g_c)
    res = stats.ttest_ind(g_t, g_c, equal_var=False)
    assert diff == pytest.approx(g_t.mean() - g_c.mean())
    assert lower == pytest.approx(res.confidence_interval(confidence_level=0.90).low)


@pytest.fixture(scope="module")
def pool():
    rng = np.random.default_rng(7)
    y = (rng.random(60000) < 0.55).astype(int)
    g = np.where(y == 1, rng.poisson(9, 60000) + 1.0, np.nan)
    return ab.Pool(pd.DataFrame({"returned_14d": y, "second_basket_size": g}))


def test_simulation_is_reproducible(pool):
    a = ab.simulate_experiment(np.random.default_rng(3), pool, 5000, effect=0.02)
    b = ab.simulate_experiment(np.random.default_rng(3), pool, 5000, effect=0.02)
    assert all(np.array_equal(x, y, equal_nan=True) for x, y in zip(a, b))


def test_injected_effect_is_recovered_and_control_untouched(pool):
    res = ab.run_many(pool, 5000, np.random.SeedSequence(5), n_sims=300, effect=0.03)
    assert res.abs_lift.mean() == pytest.approx(0.03, abs=0.003)
    assert res.rate_control.mean() == pytest.approx(pool.p0, abs=0.003)


def test_aa_false_positive_rate_near_alpha(pool):
    res = ab.run_many(pool, 5000, np.random.SeedSequence(6), n_sims=1000)
    assert abs((res.p_value < 0.05).mean() - 0.05) < 0.02


def test_guardrail_harm_blocks_shipping_and_srm_blocks_results(pool):
    harm = ab.run_many(pool, 5000, np.random.SeedSequence(8), n_sims=100, effect=0.05, harm=2.0)
    assert not harm.ship.any()
    srm = ab.run_many(pool, 5000, np.random.SeedSequence(9), n_sims=100, effect=0.05, srm_drop=0.2)
    assert srm.srm_flag.all() and not srm.ship.any()

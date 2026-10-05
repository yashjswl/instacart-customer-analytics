import numpy as np
import pandas as pd


def table(pipeline, name):
    return pd.read_csv(pipeline["out"] / "reports" / "tables" / f"{name}.csv")


def test_row_counts_reconcile_with_source(pipeline, raw_tables):
    con = pipeline["con"]
    assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == len(raw_tables["orders"])
    assert con.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == len(raw_tables["items"])
    assert con.execute("SELECT COUNT(*) FROM user_orders").fetchone()[0] == len(raw_tables["orders"])
    assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == raw_tables["orders"].user_id.nunique()


def test_validation_has_no_failures(pipeline):
    v = pd.read_csv(pipeline["out"] / "docs" / "validation.csv")
    assert not (v.status == "FAIL").any(), v[v.status == "FAIL"]


def test_validation_catches_an_orphan_key(pipeline, tmp_path):
    # break a copy of the data and check the validation notices
    import shutil
    from src import run_sql
    raw = tmp_path / "raw"
    shutil.copytree(pipeline["raw"], raw)
    prior = pd.read_csv(raw / "order_products__prior.csv")
    prior.loc[0, "order_id"] = 10**8
    prior.to_csv(raw / "order_products__prior.csv", index=False)
    con = run_sql.run(raw, tmp_path / "bad.duckdb", out_root=tmp_path,
                      files=sorted(run_sql.ROOT.glob("sql/0[01]_*.sql")))
    con.close()
    v = pd.read_csv(tmp_path / "docs" / "validation.csv")
    assert (v.status == "FAIL").any()


def test_day_offset_is_cumulative_gap_sum(pipeline, raw_tables):
    o = raw_tables["orders"].sort_values(["user_id", "order_number"])
    expected = o.groupby("user_id").days_since_prior_order.transform(lambda s: s.fillna(0).cumsum())
    got = pipeline["con"].execute(
        "SELECT order_id, day_offset, seq, order_number, prev_day_offset FROM user_orders").df().set_index("order_id")
    assert np.allclose(got.loc[o.order_id, "day_offset"].to_numpy(), expected.to_numpy())
    assert (got.seq == got.order_number).all()
    # LAG gives back the gap
    nxt = got[got.order_number > 1]
    gaps = o.set_index("order_id").loc[nxt.index, "days_since_prior_order"]
    assert np.allclose(nxt.day_offset - nxt.prev_day_offset, gaps)


def test_funnel_matches_pandas_and_never_rises(pipeline, raw_tables):
    f = table(pipeline, "funnel")
    n_orders = raw_tables["orders"].groupby("user_id").size()
    for _, row in f.iterrows():
        assert row.users_reaching == (n_orders >= row.order_k).sum()
    assert f.users_reaching.is_monotonic_decreasing
    assert f.loc[f.order_k == 1, "share_of_users"].item() == 1.0


def test_retention_matches_pandas(pipeline, raw_tables):
    o = raw_tables["orders"]
    second = o[o.order_number == 2].set_index("user_id").days_since_prior_order
    r = table(pipeline, "retention_by_segment")
    overall = r[r.segment_type == "all"].iloc[0]
    assert np.isclose(overall.retained_7d, (second <= 7).mean(), atol=1e-6)
    assert np.isclose(overall.retained_14d, (second <= 14).mean(), atol=1e-6)
    assert np.isclose(overall.retained_30d_lower, (second < 30).mean(), atol=1e-6)
    assert np.isclose(overall.share_second_gap_capped, (second == 30).mean(), atol=1e-6)
    assert np.allclose(r.retained_30d_lower + r.share_second_gap_capped, 1.0, atol=1e-5)
    assert (r.retained_7d <= r.retained_14d).all()
    assert (r.retained_14d <= r.retained_30d_lower + 1e-9).all()
    sizes = r[r.segment_type == "first_basket_size"].users.sum()
    assert sizes == len(second)


def test_return_curve_never_decreases_and_activity_curve_never_increases(pipeline):
    assert table(pipeline, "return_curve").share_returned_by_day.is_monotonic_increasing
    assert table(pipeline, "activity_curve").share_still_ordering.is_monotonic_decreasing


def test_reorder_rate_matches_pandas(pipeline, raw_tables):
    t = raw_tables
    df = (t["items"].merge(t["orders"][["order_id", "order_number"]], on="order_id")
          .merge(t["products"], on="product_id").merge(t["departments"], on="department_id"))
    df = df[df.order_number > 1]
    expected = df.groupby("department").reordered.mean()
    got = table(pipeline, "reorder_by_department").set_index("department").reorder_rate
    assert np.allclose(got.sort_index(), expected.sort_index(), atol=1e-6)


def test_affinity_metrics_match_pandas(pipeline, raw_tables):
    items = raw_tables["items"]
    n_baskets = items.order_id.nunique()
    got = table(pipeline, "affinity_top_by_lift")
    assert len(got) > 0
    baskets = items.groupby("order_id").product_id.apply(set)
    for _, r in got.head(10).iterrows():
        both = sum(1 for b in baskets if r.product_a in b and r.product_b in b)
        a = sum(1 for b in baskets if r.product_a in b)
        b_ = sum(1 for b in baskets if r.product_b in b)
        assert r.pair_orders == both
        assert np.isclose(r.confidence_a_to_b, both / a)
        assert np.isclose(r.lift, (both / n_baskets) / ((a / n_baskets) * (b_ / n_baskets)))
    assert got.lift.is_monotonic_decreasing


def test_ab_inputs_match_retention(pipeline):
    ab = pipeline["con"].execute("SELECT * FROM ab_users").df()
    r = table(pipeline, "retention_by_segment")
    assert len(ab) == pipeline["con"].execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert np.isclose(ab.returned_14d.mean(), r[r.segment_type == "all"].retained_14d.iloc[0], atol=1e-6)
    assert (ab.second_basket_size.notna() == (ab.returned_14d == 1)).all()

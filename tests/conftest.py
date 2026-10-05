"""Builds a small simulated dataset with the same schema and conventions as the Instacart files.

It is random and only exists to test the SQL and the metric code against independent pandas
calculations. No result in the README comes from it.
"""
import numpy as np
import pandas as pd
import pytest

from src import run_sql

SMALL_PARAMS = {"min_aisle_rows": 5, "min_segment_users": 5, "min_product_orders": 8, "min_pair_orders": 3}


def make_raw(raw_dir, seed=0, n_users=120, n_products=40):
    rng = np.random.default_rng(seed)
    departments = pd.DataFrame({"department_id": [1, 2, 3], "department": ["produce", "dairy", "missing"]})
    aisles = pd.DataFrame({"aisle_id": [1, 2, 3, 4], "aisle": ["fruit", "veg", "milk", "missing"]})
    products = pd.DataFrame({
        "product_id": np.arange(1, n_products + 1),
        "product_name": [f"product {i}" for i in range(1, n_products + 1)],
        "aisle_id": rng.integers(1, 5, n_products),
        "department_id": rng.integers(1, 4, n_products),
    })
    orders, prior, train = [], [], []
    order_id = 1
    for user_id in range(1, n_users + 1):
        n_orders = int(rng.integers(4, 15))
        history = set()
        for order_number in range(1, n_orders + 1):
            last = order_number == n_orders
            eval_set = ("train" if rng.random() < 0.5 else "test") if last else "prior"
            gap = np.nan if order_number == 1 else float(min(30, rng.geometric(0.12)))
            orders.append((order_id, user_id, eval_set, order_number, int(rng.integers(0, 7)),
                           int(rng.integers(0, 24)), gap))
            if eval_set != "test":
                size = int(rng.integers(1, 12))
                # popular products get picked more often, so that pair lifts are not all ~1
                weights = np.linspace(2, 0.2, n_products)
                items = rng.choice(products.product_id, size=size, replace=False, p=weights / weights.sum())
                rows = [(order_id, int(p), k + 1, int(p in history and order_number > 1))
                        for k, p in enumerate(items)]
                (prior if eval_set == "prior" else train).extend(rows)
                history.update(int(p) for p in items)
            order_id += 1
    cols = ["order_id", "product_id", "add_to_cart_order", "reordered"]
    pd.DataFrame(orders, columns=["order_id", "user_id", "eval_set", "order_number", "order_dow",
                                  "order_hour_of_day", "days_since_prior_order"]).to_csv(raw_dir / "orders.csv", index=False)
    pd.DataFrame(prior, columns=cols).to_csv(raw_dir / "order_products__prior.csv", index=False)
    pd.DataFrame(train, columns=cols).to_csv(raw_dir / "order_products__train.csv", index=False)
    products.to_csv(raw_dir / "products.csv", index=False)
    aisles.to_csv(raw_dir / "aisles.csv", index=False)
    departments.to_csv(raw_dir / "departments.csv", index=False)


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    base = tmp_path_factory.mktemp("sim")
    raw = base / "raw"
    raw.mkdir()
    make_raw(raw)
    con = run_sql.run(raw, base / "test.duckdb", out_root=base, params=SMALL_PARAMS)
    yield {"con": con, "raw": raw, "out": base}
    con.close()


@pytest.fixture(scope="session")
def raw_tables(pipeline):
    raw = pipeline["raw"]
    return {
        "orders": pd.read_csv(raw / "orders.csv"),
        "items": pd.concat([pd.read_csv(raw / "order_products__prior.csv"),
                            pd.read_csv(raw / "order_products__train.csv")]),
        "products": pd.read_csv(raw / "products.csv"),
        "departments": pd.read_csv(raw / "departments.csv"),
    }

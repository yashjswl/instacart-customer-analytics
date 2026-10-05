import argparse
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent

# Thresholds used by the SQL files. Tests pass smaller values for the tiny fixture.
DEFAULT_PARAMS = {
    "min_aisle_rows": 10000,      # 05: minimum line items for an aisle/department to be reported as reliable
    "min_segment_users": 1000,    # 04: minimum users for a retention segment to be reported as reliable
    "min_product_orders": 20000,  # 06: a product must appear in this many baskets to enter pair analysis
    "min_pair_orders": 500,       # 06: a pair must co-occur in this many baskets to be reported
}

EXPORT = re.compile(r"^\s*--\s*export:\s*(\S+)\s*$", re.MULTILINE)


def split_statements(sql):
    # SQL files must not contain ';' inside comments or string literals.
    return [s for s in sql.split(";") if re.sub(r"--[^\n]*", "", s).strip()]


def run(raw_dir, db_path, out_root=ROOT, params=None, files=None):
    params = {**DEFAULT_PARAMS, **(params or {})}
    subs = {"raw_dir": str(Path(raw_dir).resolve()), **{k: str(v) for k, v in params.items()}}
    con = duckdb.connect(str(db_path))
    sql_files = files or sorted((ROOT / "sql").glob("*.sql"))
    for path in sql_files:
        text = Path(path).read_text()
        for key, value in subs.items():
            text = text.replace("{{" + key + "}}", value)
        for stmt in split_statements(text):
            target = EXPORT.search(stmt)
            if target:
                out = Path(out_root) / target.group(1)
                out.parent.mkdir(parents=True, exist_ok=True)
                df = con.execute(stmt).df()
                df.to_csv(out, index=False)
                print(f"{Path(path).name}: wrote {out.relative_to(out_root)} ({len(df)} rows)")
            else:
                con.execute(stmt)
        print(f"ran {Path(path).name}")
    return con


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=ROOT / "data" / "raw")
    ap.add_argument("--db", default=ROOT / "data" / "instacart.duckdb")
    args = ap.parse_args()
    run(args.raw_dir, args.db).close()

# Assumptions and data caveats

- **No calendar dates.** Only `order_number`, `order_dow`, `order_hour_of_day` and `days_since_prior_order` exist. There are no calendar cohorts, no seasonality and no trends over real time.
- **Capped gaps.** `days_since_prior_order` stops at 30. Day offsets and "time to order k" are lower bounds for users with long gaps. The number of capped gaps is recorded in `docs/validation.csv`.
- **Sample selection.** Each user has at least 4 orders (checked in validation). The funnel and retention rates therefore describe customers who stayed, not everyone who ever placed a first order, and they overstate retention for a general sign-up population.
- **Test-set orders.** The last order of some users is labelled `test` and has no line items. These orders count in the funnel and timeline but not in anything that needs a basket (reorder rate, affinity, basket size).
- **No prices.** There is no price column, so there is no revenue or basket value analysis, only item counts.
- **Placeholder categories.** The catalog has aisle and department values named `missing` and `other`. They are kept in the outputs and are not real categories.
- **Thresholds are my choices.** Minimum support values (see `src/run_sql.py`) were set to avoid noisy rates, not tuned to produce a result. They are written in the SQL output as flags so the cut is visible.
- **Tests use simulated data.** `tests/conftest.py` builds a small random dataset in the same format to check the SQL against independent pandas calculations. Nothing in the results comes from it.

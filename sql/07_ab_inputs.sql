-- Real user outcomes that the simulated experiment in src/ab_test.py starts from.
-- returned_14d: second order within 14 days of the first (primary metric, control outcome).
-- second_basket_size: items in that second order, only when it fell inside the 14 days (guardrail).
-- No experiment exists in the data, treatment effects are injected in Python and labelled simulated.

CREATE OR REPLACE TABLE ab_users AS
SELECT
    f.user_id,
    (f.days_to_second <= 14)::INT AS returned_14d,
    CASE WHEN f.days_to_second <= 14 THEN o2.basket_size END AS second_basket_size
FROM first_return f
JOIN user_orders o2 ON o2.user_id = f.user_id AND o2.order_number = 2;

-- export: reports/tables/ab_baseline.csv

SELECT
    COUNT(*) AS users,
    AVG(returned_14d) AS baseline_14d_reorder_rate,
    COUNT(second_basket_size) AS users_with_guardrail_value,
    AVG(second_basket_size) AS guardrail_mean_items,
    STDDEV_SAMP(second_basket_size) AS guardrail_sd_items
FROM ab_users;

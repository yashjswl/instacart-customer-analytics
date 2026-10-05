-- Builds a relative timeline per user. The data has no calendar dates, so a user's day
-- offset is the running sum of days_since_prior_order (first order = day 0).
-- days_since_prior_order is capped at 30, so a recorded 30 means "30 or more" and day_offset
-- can understate real elapsed time for users with long gaps. See docs/assumptions.md.

CREATE OR REPLACE TABLE basket_sizes AS
SELECT order_id, COUNT(*) AS basket_size
FROM order_items
GROUP BY order_id;

CREATE OR REPLACE TABLE user_orders AS
WITH timeline AS (
    SELECT
        o.user_id, o.order_id, o.order_number, o.eval_set, o.order_dow, o.order_hour_of_day,
        o.days_since_prior_order,
        ROW_NUMBER() OVER w AS seq,
        SUM(COALESCE(o.days_since_prior_order, 0)) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS day_offset
    FROM orders o
    WINDOW w AS (PARTITION BY o.user_id ORDER BY o.order_number)
)
SELECT
    t.*,
    LAG(t.day_offset) OVER (PARTITION BY t.user_id ORDER BY t.order_number) AS prev_day_offset,
    (t.days_since_prior_order = 30) AS gap_is_capped,
    b.basket_size  -- NULL for eval_set = 'test' orders, which have no line items
FROM timeline t
LEFT JOIN basket_sizes b USING (order_id);

CREATE OR REPLACE TABLE users AS
SELECT
    user_id,
    COUNT(*) AS n_orders,
    MAX(day_offset) AS last_day_offset,
    COUNT(*) FILTER (WHERE gap_is_capped) AS n_capped_gaps,
    MAX(basket_size) FILTER (WHERE order_number = 1) AS first_basket_size,
    MAX(order_id) FILTER (WHERE order_number = 1) AS first_order_id
FROM user_orders
GROUP BY user_id;

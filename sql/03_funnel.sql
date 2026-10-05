-- Business question: how many customers keep ordering after their first order?
-- Definition: a user "reaches order k" if they have an order with order_number >= k.
-- Edge cases: every user in this dataset has at least 4 orders (checked in 01_validation), so
-- reaching orders 2 and 3 is 100% by construction of the sample. Only the later steps carry
-- information, and the funnel describes retained customers, not all sign-ups.
-- export: reports/tables/funnel.csv

WITH steps AS (
    SELECT
        k.order_k,
        SUM((u.n_orders >= k.order_k)::INT) AS users_reaching,
        COUNT(*) AS total_users
    FROM (VALUES (1), (2), (3), (5), (10)) AS k(order_k)
    CROSS JOIN users u
    GROUP BY k.order_k
)
SELECT
    order_k,
    users_reaching,
    total_users,
    ROUND(users_reaching / total_users, 6) AS share_of_users,
    ROUND(users_reaching / LAG(users_reaching) OVER (ORDER BY order_k), 6) AS share_of_previous_step
FROM steps
ORDER BY order_k;

-- How long it takes to get there, among users who do. Gaps are capped at 30 days, so these are
-- lower bounds for users with long gaps.
-- export: reports/tables/funnel_timing.csv

SELECT
    k.order_k,
    COUNT(*) AS users,
    QUANTILE_CONT(uo.day_offset, 0.25) AS p25_days_since_first,
    QUANTILE_CONT(uo.day_offset, 0.50) AS median_days_since_first,
    QUANTILE_CONT(uo.day_offset, 0.75) AS p75_days_since_first
FROM (VALUES (2), (3), (5), (10)) AS k(order_k)
JOIN user_orders uo ON uo.order_number = k.order_k
GROUP BY k.order_k
ORDER BY k.order_k;

-- Business question: how quickly do new customers place a second order, and does the first
-- basket predict it?
-- Definition: retained within N days = the user's second order has days_since_prior_order <= N.
-- A second order on the same day (gap 0) counts. There are no calendar dates, so this is time
-- since the user's own first order, not a calendar cohort.
-- Edge cases: a gap of 30 means "30 or more" (cap). For N = 30 we report only a lower bound
-- (gap < 30) and the share of second gaps sitting at the cap. An upper bound would be 100%
-- by construction. Every user in the sample eventually reorders (min 4 orders), so these
-- rates are conditional on being a user who stayed.

CREATE OR REPLACE TABLE first_return AS
SELECT u.user_id, u.first_order_id, u.first_basket_size, o2.days_since_prior_order AS days_to_second
FROM users u
LEFT JOIN user_orders o2 ON o2.user_id = u.user_id AND o2.order_number = 2;

-- Department with the most items in the first basket, ties go to the lowest department_id.
CREATE OR REPLACE TABLE first_top_department AS
SELECT user_id, department
FROM (
    SELECT
        f.user_id, d.department,
        ROW_NUMBER() OVER (PARTITION BY f.user_id ORDER BY COUNT(*) DESC, d.department_id) AS rn
    FROM first_return f
    JOIN order_items i ON i.order_id = f.first_order_id
    JOIN products p USING (product_id)
    JOIN departments d USING (department_id)
    GROUP BY f.user_id, d.department_id, d.department
)
WHERE rn = 1;

-- Segments: overall, first-basket size bucket, top department of the first basket.
-- Segments below the minimum user count are kept but flagged.
-- export: reports/tables/retention_by_segment.csv

WITH seg AS (
    SELECT f.user_id, f.days_to_second, 'all' AS segment_type, 'all' AS segment
    FROM first_return f
    UNION ALL
    SELECT f.user_id, f.days_to_second, 'first_basket_size',
        CASE WHEN f.first_basket_size <= 5 THEN '1-5 items'
             WHEN f.first_basket_size <= 10 THEN '6-10 items'
             WHEN f.first_basket_size <= 20 THEN '11-20 items'
             ELSE '21+ items' END
    FROM first_return f
    UNION ALL
    SELECT f.user_id, f.days_to_second, 'first_basket_top_department', t.department
    FROM first_return f JOIN first_top_department t USING (user_id)
)
SELECT
    segment_type, segment,
    COUNT(*) AS users,
    ROUND(AVG((days_to_second <= 7)::INT), 6) AS retained_7d,
    ROUND(AVG((days_to_second <= 14)::INT), 6) AS retained_14d,
    ROUND(AVG((days_to_second < 30)::INT), 6) AS retained_30d_lower,
    ROUND(AVG((days_to_second = 30)::INT), 6) AS share_second_gap_capped,
    COUNT(*) >= {{min_segment_users}} AS meets_min_users
FROM seg
GROUP BY segment_type, segment
ORDER BY segment_type, segment;

-- Cumulative return curve: share of users whose second order came by day d. Never decreases.
-- Stops at day 29 because a recorded 30 is censored.
-- export: reports/tables/return_curve.csv

SELECT d.day, ROUND(AVG((f.days_to_second <= d.day)::INT), 6) AS share_returned_by_day
FROM generate_series(0, 29) AS d(day)
CROSS JOIN first_return f
GROUP BY d.day
ORDER BY d.day;

-- Activity curve: share of users who still have an order on or after day d since their first
-- order. Never increases. Day offsets are understated when gaps are capped.
-- export: reports/tables/activity_curve.csv

SELECT d.day, ROUND(AVG((u.last_day_offset >= d.day)::INT), 6) AS share_still_ordering
FROM generate_series(0, 360, 30) AS d(day)
CROSS JOIN users u
GROUP BY d.day
ORDER BY d.day;

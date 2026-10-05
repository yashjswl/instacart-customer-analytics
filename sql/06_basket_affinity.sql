-- Business question: which products are bought together beyond what their popularity explains?
-- Definitions, with N = number of baskets (orders with line items):
--   support(A,B)    = baskets containing both / N
--   confidence(A->B) = baskets containing both / baskets containing A
--   lift(A,B)       = support(A,B) / (support(A) * support(B))
-- Why raw counts mislead: the most common pairs are just the most popular products (bananas,
-- organic bags) appearing together because they appear everywhere. Lift divides that out: 1 means
-- independent, above 1 means they co-occur more than chance.
-- Edge cases: only products in at least {{min_product_orders}} baskets are considered, and only pairs
-- seen together in at least {{min_pair_orders}} baskets are reported, because lift is unstable for rare items.
-- Pairs are unordered (product_a < product_b), confidence is given in both directions.

CREATE OR REPLACE TABLE affinity_items AS
SELECT product_id, COUNT(*) AS item_orders
FROM order_items
GROUP BY product_id
HAVING COUNT(*) >= {{min_product_orders}};

CREATE OR REPLACE TABLE affinity_pairs AS
WITH n AS (SELECT COUNT(DISTINCT order_id) AS baskets FROM order_items),
eligible AS (
    SELECT i.order_id, i.product_id
    FROM order_items i
    JOIN affinity_items USING (product_id)
),
pairs AS (
    SELECT a.product_id AS product_a, b.product_id AS product_b, COUNT(*) AS pair_orders
    FROM eligible a
    JOIN eligible b ON a.order_id = b.order_id AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    HAVING COUNT(*) >= {{min_pair_orders}}
)
SELECT
    pa.product_name AS product_a_name, pb.product_name AS product_b_name,
    p.product_a, p.product_b, p.pair_orders,
    p.pair_orders / n.baskets AS support,
    p.pair_orders / ia.item_orders AS confidence_a_to_b,
    p.pair_orders / ib.item_orders AS confidence_b_to_a,
    (p.pair_orders / n.baskets) / ((ia.item_orders / n.baskets) * (ib.item_orders / n.baskets)) AS lift
FROM pairs p
CROSS JOIN n
JOIN affinity_items ia ON ia.product_id = p.product_a
JOIN affinity_items ib ON ib.product_id = p.product_b
JOIN products pa ON pa.product_id = p.product_a
JOIN products pb ON pb.product_id = p.product_b;

-- export: reports/tables/affinity_top_by_count.csv

SELECT * FROM affinity_pairs ORDER BY pair_orders DESC, product_a, product_b LIMIT 50;

-- export: reports/tables/affinity_top_by_lift.csv

SELECT * FROM affinity_pairs ORDER BY lift DESC, product_a, product_b LIMIT 50;

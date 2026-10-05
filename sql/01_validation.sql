-- Integrity checks on the raw tables. status is PASS/FAIL when there is an expected value,
-- INFO when the number is only recorded for the docs.
-- export: docs/validation.csv

WITH checks(check_name, observed, expected) AS (
    SELECT 'rows: orders', COUNT(*), NULL FROM orders
    UNION ALL SELECT 'rows: order_products__prior', COUNT(*), NULL FROM order_products_prior
    UNION ALL SELECT 'rows: order_products__train', COUNT(*), NULL FROM order_products_train
    UNION ALL SELECT 'rows: products', COUNT(*), NULL FROM products
    UNION ALL SELECT 'rows: aisles', COUNT(*), NULL FROM aisles
    UNION ALL SELECT 'rows: departments', COUNT(*), NULL FROM departments

    -- key uniqueness
    UNION ALL SELECT 'duplicate order_id in orders', COUNT(*) - COUNT(DISTINCT order_id), 0 FROM orders
    UNION ALL SELECT 'duplicate (order_id, product_id) in prior',
        COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, product_id FROM order_products_prior)), 0
        FROM order_products_prior
    UNION ALL SELECT 'duplicate (order_id, product_id) in train',
        COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, product_id FROM order_products_train)), 0
        FROM order_products_train
    UNION ALL SELECT 'duplicate (user_id, order_number) in orders',
        COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT user_id, order_number FROM orders)), 0 FROM orders
    UNION ALL SELECT 'duplicate product_id in products', COUNT(*) - COUNT(DISTINCT product_id), 0 FROM products
    UNION ALL SELECT 'duplicate aisle_id in aisles', COUNT(*) - COUNT(DISTINCT aisle_id), 0 FROM aisles
    UNION ALL SELECT 'duplicate department_id in departments', COUNT(*) - COUNT(DISTINCT department_id), 0 FROM departments

    -- orphan keys
    UNION ALL SELECT 'prior rows with order_id not in orders', COUNT(*), 0
        FROM order_products_prior p WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = p.order_id)
    UNION ALL SELECT 'train rows with order_id not in orders', COUNT(*), 0
        FROM order_products_train p WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = p.order_id)
    UNION ALL SELECT 'order_items rows with product_id not in products', COUNT(*), 0
        FROM order_items i WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = i.product_id)
    UNION ALL SELECT 'products with aisle_id not in aisles', COUNT(*), 0
        FROM products p WHERE NOT EXISTS (SELECT 1 FROM aisles a WHERE a.aisle_id = p.aisle_id)
    UNION ALL SELECT 'products with department_id not in departments', COUNT(*), 0
        FROM products p WHERE NOT EXISTS (SELECT 1 FROM departments d WHERE d.department_id = p.department_id)

    -- eval_set consistency: prior rows belong to prior orders, train rows to train orders, test has none
    UNION ALL SELECT 'prior rows whose order is not eval_set=prior', COUNT(*), 0
        FROM order_products_prior p JOIN orders o USING (order_id) WHERE o.eval_set <> 'prior'
    UNION ALL SELECT 'train rows whose order is not eval_set=train', COUNT(*), 0
        FROM order_products_train p JOIN orders o USING (order_id) WHERE o.eval_set <> 'train'
    UNION ALL SELECT 'prior orders with no line items', COUNT(*), 0
        FROM orders o WHERE o.eval_set = 'prior'
        AND NOT EXISTS (SELECT 1 FROM order_products_prior p WHERE p.order_id = o.order_id)
    UNION ALL SELECT 'train orders with no line items', COUNT(*), 0
        FROM orders o WHERE o.eval_set = 'train'
        AND NOT EXISTS (SELECT 1 FROM order_products_train p WHERE p.order_id = o.order_id)
    UNION ALL SELECT 'orders with eval_set=test (no line items by design)', COUNT(*), NULL
        FROM orders WHERE eval_set = 'test'

    -- nulls
    UNION ALL SELECT 'null in orders key/time columns',
        COUNT(*) FILTER (WHERE order_id IS NULL OR user_id IS NULL OR eval_set IS NULL
            OR order_number IS NULL OR order_dow IS NULL OR order_hour_of_day IS NULL), 0 FROM orders
    UNION ALL SELECT 'null days_since_prior_order where order_number > 1',
        COUNT(*) FILTER (WHERE order_number > 1 AND days_since_prior_order IS NULL), 0 FROM orders
    UNION ALL SELECT 'non-null days_since_prior_order where order_number = 1',
        COUNT(*) FILTER (WHERE order_number = 1 AND days_since_prior_order IS NOT NULL), 0 FROM orders
    UNION ALL SELECT 'null in order_items columns',
        COUNT(*) FILTER (WHERE order_id IS NULL OR product_id IS NULL
            OR add_to_cart_order IS NULL OR reordered IS NULL), 0 FROM order_items
    UNION ALL SELECT 'null in products columns',
        COUNT(*) FILTER (WHERE product_name IS NULL OR aisle_id IS NULL OR department_id IS NULL), 0 FROM products

    -- ranges
    UNION ALL SELECT 'order_dow outside 0-6', COUNT(*) FILTER (WHERE order_dow NOT BETWEEN 0 AND 6), 0 FROM orders
    UNION ALL SELECT 'order_hour_of_day outside 0-23',
        COUNT(*) FILTER (WHERE order_hour_of_day NOT BETWEEN 0 AND 23), 0 FROM orders
    UNION ALL SELECT 'days_since_prior_order outside 0-30',
        COUNT(*) FILTER (WHERE days_since_prior_order < 0 OR days_since_prior_order > 30), 0 FROM orders
    UNION ALL SELECT 'reordered not in (0, 1)', COUNT(*) FILTER (WHERE reordered NOT IN (0, 1)), 0 FROM order_items

    -- timeline shape
    UNION ALL SELECT 'users whose order_number is not 1..n without gaps',
        COUNT(*), 0 FROM (SELECT user_id FROM orders GROUP BY user_id
            HAVING MIN(order_number) <> 1 OR MAX(order_number) <> COUNT(*))

    -- facts that shape the analysis (recorded, not pass/fail)
    UNION ALL SELECT 'users', COUNT(DISTINCT user_id), NULL FROM orders
    UNION ALL SELECT 'min orders per user', MIN(n), NULL FROM (SELECT COUNT(*) AS n FROM orders GROUP BY user_id)
    UNION ALL SELECT 'max orders per user', MAX(n), NULL FROM (SELECT COUNT(*) AS n FROM orders GROUP BY user_id)
    UNION ALL SELECT 'orders with days_since_prior_order = 30 (cap)',
        COUNT(*) FILTER (WHERE days_since_prior_order = 30), NULL FROM orders
    UNION ALL SELECT 'products in aisle/department named "missing"',
        COUNT(*) FILTER (WHERE a.aisle = 'missing' OR d.department = 'missing'), NULL
        FROM products p JOIN aisles a USING (aisle_id) JOIN departments d USING (department_id)
)
SELECT check_name, observed, expected,
    CASE WHEN expected IS NULL THEN 'INFO'
         WHEN observed = expected THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks;

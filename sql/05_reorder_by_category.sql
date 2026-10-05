-- Business question: which parts of the catalog are bought out of habit, and which are
-- bought once and rarely again?
-- Definition: reorder rate = share of line items with reordered = 1, counted only in orders
-- with order_number > 1. A first order cannot contain a reorder, so including it would pull
-- every rate down. Prior and train line items are both used (test orders have none).
-- Edge cases: the minimum support is {{min_aisle_rows}} line items. Smaller groups are kept
-- with meets_min_support = false so the cut is visible. 'missing' and 'other' are catalog
-- placeholders, not real categories.
-- export: reports/tables/reorder_by_department.csv

SELECT
    d.department,
    COUNT(*) AS line_items,
    ROUND(AVG(i.reordered), 6) AS reorder_rate,
    COUNT(*) >= {{min_aisle_rows}} AS meets_min_support
FROM order_items i
JOIN orders o USING (order_id)
JOIN products p USING (product_id)
JOIN departments d USING (department_id)
WHERE o.order_number > 1
GROUP BY d.department
ORDER BY reorder_rate DESC, d.department;

-- export: reports/tables/reorder_by_aisle.csv

SELECT
    d.department, a.aisle,
    COUNT(*) AS line_items,
    ROUND(AVG(i.reordered), 6) AS reorder_rate,
    COUNT(*) >= {{min_aisle_rows}} AS meets_min_support
FROM order_items i
JOIN orders o USING (order_id)
JOIN products p USING (product_id)
JOIN aisles a USING (aisle_id)
JOIN departments d USING (department_id)
WHERE o.order_number > 1
GROUP BY d.department, a.aisle
ORDER BY reorder_rate DESC, a.aisle;

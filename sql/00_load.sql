-- Loads the six raw CSVs into DuckDB. {{raw_dir}} is filled in by src/run_sql.py.
-- Types are set explicitly so a bad value fails the load instead of being guessed.

CREATE OR REPLACE TABLE orders AS
SELECT * FROM read_csv('{{raw_dir}}/orders.csv', header = true, columns = {
    'order_id': 'INTEGER', 'user_id': 'INTEGER', 'eval_set': 'VARCHAR',
    'order_number': 'SMALLINT', 'order_dow': 'SMALLINT',
    'order_hour_of_day': 'SMALLINT', 'days_since_prior_order': 'DOUBLE'});

CREATE OR REPLACE TABLE order_products_prior AS
SELECT * FROM read_csv('{{raw_dir}}/order_products__prior.csv', header = true, columns = {
    'order_id': 'INTEGER', 'product_id': 'INTEGER',
    'add_to_cart_order': 'SMALLINT', 'reordered': 'SMALLINT'});

CREATE OR REPLACE TABLE order_products_train AS
SELECT * FROM read_csv('{{raw_dir}}/order_products__train.csv', header = true, columns = {
    'order_id': 'INTEGER', 'product_id': 'INTEGER',
    'add_to_cart_order': 'SMALLINT', 'reordered': 'SMALLINT'});

CREATE OR REPLACE TABLE products AS
SELECT * FROM read_csv('{{raw_dir}}/products.csv', header = true, columns = {
    'product_id': 'INTEGER', 'product_name': 'VARCHAR',
    'aisle_id': 'INTEGER', 'department_id': 'INTEGER'});

CREATE OR REPLACE TABLE aisles AS
SELECT * FROM read_csv('{{raw_dir}}/aisles.csv', header = true, columns = {
    'aisle_id': 'INTEGER', 'aisle': 'VARCHAR'});

CREATE OR REPLACE TABLE departments AS
SELECT * FROM read_csv('{{raw_dir}}/departments.csv', header = true, columns = {
    'department_id': 'INTEGER', 'department': 'VARCHAR'});

-- Every line item we have. Test-set orders (the last order of some users) have no rows anywhere.
CREATE OR REPLACE VIEW order_items AS
SELECT * FROM order_products_prior
UNION ALL
SELECT * FROM order_products_train;

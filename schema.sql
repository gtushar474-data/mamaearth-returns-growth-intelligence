-- Mamaearth Returns & Growth Intelligence Pipeline
-- Run from project root: sqlite3 mamaearth.db < sql/schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    city TEXT NOT NULL,
    city_tier INTEGER NOT NULL,
    signup_date TEXT NOT NULL,
    acquisition_source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    discount_pct REAL DEFAULT 0 CHECK (discount_pct BETWEEN 0 AND 100),
    payment_method TEXT NOT NULL,
    rating REAL CHECK (rating BETWEEN 1 AND 5),
    is_returned INTEGER NOT NULL DEFAULT 0 CHECK (is_returned IN (0,1)),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

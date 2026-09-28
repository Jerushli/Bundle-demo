-- Bundle Data Assistant V2: scale-test data for a SEPARATE Neon database/branch.
-- Run the existing schema file first. This script preserves the five demo rows.
-- NEVER run against the database used by the live Render deployment.
-- Expected starting state: exactly 5 orders; script intentionally refuses to rerun.

BEGIN;

DO $$
BEGIN
    IF (SELECT COUNT(*) FROM orders) <> 5 THEN
        RAISE EXCEPTION 'Expected exactly 5 starting orders. Aborting to protect existing data.';
    END IF;
END;
$$;

-- Preserve Alpha and Beta; add providers 3 through 20.
INSERT INTO providers (provider_id, provider_name)
SELECT n, 'Provider ' || LPAD(n::text, 2, '0')
FROM generate_series(3, 20) AS g(n)
ON CONFLICT (provider_id) DO NOTHING;

-- IDs 1 through 5 already exist. Insert 999,995 additional fictional orders.
-- All generated dates are within 2026-01-01 through 2026-09-24 inclusive.
INSERT INTO orders (order_id, provider_id, order_date)
SELECT
    n,
    1 + floor(random() * 20)::integer,
    DATE '2026-01-01' + floor(random() * 267)::integer
FROM generate_series(6, 1000000) AS g(n);

-- Help date-filtered aggregation queries; assess effectiveness with EXPLAIN later.
CREATE INDEX IF NOT EXISTS idx_orders_order_date_provider
    ON orders (order_date, provider_id);

COMMIT;

ANALYZE orders;
ANALYZE providers;

SELECT COUNT(*) AS total_orders FROM orders;
SELECT COUNT(*) AS total_providers FROM providers;
SELECT MIN(order_date) AS earliest_order, MAX(order_date) AS latest_order FROM orders;

CREATE SCHEMA IF NOT EXISTS bundle;

CREATE TABLE IF NOT EXISTS bundle.dataset_registry (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL
        UNIQUE,

    display_name VARCHAR(200) NOT NULL,

    source_type VARCHAR(50) NOT NULL
        DEFAULT 'csv',

    source_name TEXT,

    analytics_table VARCHAR(200),

    status VARCHAR(30) NOT NULL
        DEFAULT 'registered'
        CHECK (
            status IN (
                'registered',
                'ingesting',
                'profiled',
                'validated',
                'transforming',
                'ready',
                'failed'
            )
        ),

    row_count BIGINT,

    is_active BOOLEAN NOT NULL
        DEFAULT FALSE,

    last_refreshed_at TIMESTAMPTZ,

    activated_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    error_message TEXT
);

-- PostgreSQL partial unique index:
-- at most one registry row can be active.
CREATE UNIQUE INDEX IF NOT EXISTS
    dataset_registry_one_active_idx
ON bundle.dataset_registry (
    is_active
)
WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS
    dataset_registry_status_idx
ON bundle.dataset_registry (
    status
);

-- ------------------------------------------------------------
-- Register the existing Bundle v2 development dataset.
-- ------------------------------------------------------------

INSERT INTO bundle.dataset_registry
(
    dataset_name,
    display_name,
    source_type,
    source_name,
    analytics_table,
    status,
    row_count,
    is_active,
    last_refreshed_at,
    activated_at
)
VALUES
(
    'bundle_test_sales',
    'Bundle Test Sales',
    'csv',
    'bundle_test_sales.csv',
    'analytics.bundle_test_sales_clean',
    'ready',
    NULL,
    TRUE,
    now(),
    now()
)
ON CONFLICT (dataset_name)
DO UPDATE SET
    display_name =
        EXCLUDED.display_name,
    source_type =
        EXCLUDED.source_type,
    source_name =
        EXCLUDED.source_name,
    analytics_table =
        EXCLUDED.analytics_table,
    status =
        EXCLUDED.status,
    is_active =
        TRUE,
    last_refreshed_at =
        COALESCE(
            bundle.dataset_registry.last_refreshed_at,
            now()
        ),
    activated_at =
        COALESCE(
            bundle.dataset_registry.activated_at,
            now()
        ),
    updated_at =
        now();

-- If the clean analytics table exists, populate the exact row count.
DO $$
BEGIN
    IF to_regclass(
        'analytics.bundle_test_sales_clean'
    ) IS NOT NULL THEN

        UPDATE bundle.dataset_registry
        SET
            row_count = (
                SELECT COUNT(*)
                FROM analytics.bundle_test_sales_clean
            ),
            updated_at = now()
        WHERE
            dataset_name = 'bundle_test_sales';
    END IF;
END
$$;

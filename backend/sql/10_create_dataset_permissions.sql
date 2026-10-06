CREATE SCHEMA IF NOT EXISTS security;

CREATE TABLE IF NOT EXISTS security.dataset_permissions (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    role VARCHAR(20) NOT NULL
        CHECK (
            role IN (
                'admin',
                'analyst',
                'viewer'
            )
        ),

    can_read BOOLEAN NOT NULL
        DEFAULT FALSE,

    allowed_columns TEXT[],

    allowed_operations TEXT[] NOT NULL
        DEFAULT ARRAY[
            'aggregate',
            'group',
            'compare',
            'trend'
        ]::TEXT[],

    max_result_rows INTEGER NOT NULL
        DEFAULT 20
        CHECK (
            max_result_rows >= 1
            AND max_result_rows <= 100
        ),

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    UNIQUE (
        dataset_name,
        role
    )
);

CREATE INDEX IF NOT EXISTS
    dataset_permissions_dataset_role_idx
ON security.dataset_permissions (
    dataset_name,
    role
);

-- ---------------------------------------------------------
-- DEVELOPMENT PERMISSIONS FOR CURRENT TEST DATASET
-- ---------------------------------------------------------

INSERT INTO security.dataset_permissions (
    dataset_name,
    role,
    can_read,
    allowed_columns,
    allowed_operations,
    max_result_rows
)
VALUES
(
    'bundle_test_sales',
    'admin',
    TRUE,
    NULL,
    ARRAY[
        'aggregate',
        'group',
        'compare',
        'trend'
    ]::TEXT[],
    100
),
(
    'bundle_test_sales',
    'analyst',
    TRUE,
    ARRAY[
        'transaction_id',
        'date',
        'country',
        'region',
        'segment',
        'customer_id',
        'product',
        'units_sold',
        'sale_price',
        'sales',
        'cogs',
        'profit',
        'discount_band',
        'discount_amount'
    ]::TEXT[],
    ARRAY[
        'aggregate',
        'group',
        'compare',
        'trend'
    ]::TEXT[],
    20
),
(
    'bundle_test_sales',
    'viewer',
    TRUE,
    ARRAY[
        'date',
        'country',
        'region',
        'segment',
        'product',
        'sales',
        'profit'
    ]::TEXT[],
    ARRAY[
        'aggregate',
        'group'
    ]::TEXT[],
    10
)
ON CONFLICT (
    dataset_name,
    role
)
DO UPDATE SET
    can_read = EXCLUDED.can_read,
    allowed_columns = EXCLUDED.allowed_columns,
    allowed_operations = EXCLUDED.allowed_operations,
    max_result_rows = EXCLUDED.max_result_rows,
    updated_at = now();

CREATE SCHEMA IF NOT EXISTS bundle;

CREATE TABLE IF NOT EXISTS bundle.business_rules (
    id BIGSERIAL PRIMARY KEY,

    rule_name VARCHAR(120) NOT NULL UNIQUE,

    numeric_value DOUBLE PRECISION NOT NULL,

    unit VARCHAR(40) NOT NULL,

    description TEXT NOT NULL
        DEFAULT '',

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    updated_by VARCHAR(200),

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

INSERT INTO bundle.business_rules
(
    rule_name,
    numeric_value,
    unit,
    description,
    is_active,
    updated_by
)
VALUES
(
    'investment_hurdle_rate_percent',
    15,
    'percent',
    'Minimum acceptable scenario ROI for investment-rule evaluation.',
    TRUE,
    'system_migration'
),
(
    'investment_max_payback_months',
    24,
    'months',
    'Maximum acceptable payback period for investment-rule evaluation.',
    TRUE,
    'system_migration'
),
(
    'investment_default_baseline_period_months',
    12,
    'months',
    'Default number of months represented by the observed baseline.',
    TRUE,
    'system_migration'
)
ON CONFLICT (
    rule_name
)
DO NOTHING;

CREATE INDEX IF NOT EXISTS
    business_rules_active_idx
ON bundle.business_rules (
    is_active,
    rule_name
);

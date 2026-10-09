CREATE TABLE IF NOT EXISTS bundle.scoped_business_rules (
    id BIGSERIAL PRIMARY KEY,
    scope_type VARCHAR(80) NOT NULL,
    scope_value VARCHAR(300) NOT NULL,
    rule_name VARCHAR(120) NOT NULL,
    numeric_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(40) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope_type, scope_value, rule_name)
);

CREATE INDEX IF NOT EXISTS scoped_business_rules_lookup_idx
ON bundle.scoped_business_rules (
    scope_type,
    scope_value,
    rule_name,
    is_active
);

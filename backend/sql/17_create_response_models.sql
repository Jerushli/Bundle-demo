CREATE TABLE IF NOT EXISTS bundle.response_models (
    id BIGSERIAL PRIMARY KEY,

    model_name VARCHAR(200) NOT NULL,

    input_variable VARCHAR(120) NOT NULL,

    output_variable VARCHAR(120) NOT NULL,

    scope_type VARCHAR(80),
    scope_value VARCHAR(300),

    model_type VARCHAR(40) NOT NULL
        CHECK (
            model_type IN (
                'elasticity',
                'linear_percent'
            )
        ),

    coefficient DOUBLE PRECISION NOT NULL,

    intercept DOUBLE PRECISION NOT NULL
        DEFAULT 0,

    training_start DATE,
    training_end DATE,

    sample_size INTEGER,

    validation_metric_name VARCHAR(120),
    validation_metric_value DOUBLE PRECISION,

    confidence_level VARCHAR(20) NOT NULL
        CHECK (
            confidence_level IN (
                'low',
                'medium',
                'high'
            )
        ),

    validation_status VARCHAR(20) NOT NULL
        CHECK (
            validation_status IN (
                'draft',
                'validated',
                'retired'
            )
        ),

    version INTEGER NOT NULL
        DEFAULT 1,

    notes TEXT NOT NULL
        DEFAULT '',

    created_by VARCHAR(200),
    updated_by VARCHAR(200),

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    CHECK (
        (
            scope_type IS NULL
            AND scope_value IS NULL
        )
        OR
        (
            scope_type IS NOT NULL
            AND scope_value IS NOT NULL
        )
    ),

    CHECK (
        sample_size IS NULL
        OR sample_size > 0
    ),

    CHECK (
        version >= 1
    )
);

CREATE INDEX IF NOT EXISTS
    response_models_lookup_idx
ON bundle.response_models (
    input_variable,
    output_variable,
    scope_type,
    scope_value,
    validation_status,
    version DESC
);

CREATE UNIQUE INDEX IF NOT EXISTS
    response_models_version_unique_idx
ON bundle.response_models (
    model_name,
    version,
    COALESCE(scope_type, ''),
    COALESCE(scope_value, '')
);

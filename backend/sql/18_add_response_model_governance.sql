ALTER TABLE bundle.response_models
    ADD COLUMN IF NOT EXISTS min_input_change_percent DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS max_input_change_percent DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS validated_at DATE,
    ADD COLUMN IF NOT EXISTS max_age_days INTEGER,
    ADD COLUMN IF NOT EXISTS expires_at DATE,
    ADD COLUMN IF NOT EXISTS validation_methodology VARCHAR(40)
        NOT NULL DEFAULT 'unspecified',
    ADD COLUMN IF NOT EXISTS causal_evidence_level VARCHAR(30)
        NOT NULL DEFAULT 'associational',
    ADD COLUMN IF NOT EXISTS drift_status VARCHAR(20)
        NOT NULL DEFAULT 'not_checked',
    ADD COLUMN IF NOT EXISTS last_drift_check_at TIMESTAMPTZ;

UPDATE bundle.response_models
SET validated_at = COALESCE(
    validated_at,
    training_end,
    created_at::date
)
WHERE validation_status = 'validated'
  AND validated_at IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'response_models_input_range_check'
    ) THEN
        ALTER TABLE bundle.response_models
            ADD CONSTRAINT response_models_input_range_check
            CHECK (
                min_input_change_percent IS NULL
                OR max_input_change_percent IS NULL
                OR min_input_change_percent <= max_input_change_percent
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'response_models_max_age_days_check'
    ) THEN
        ALTER TABLE bundle.response_models
            ADD CONSTRAINT response_models_max_age_days_check
            CHECK (
                max_age_days IS NULL
                OR max_age_days > 0
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'response_models_validation_methodology_check'
    ) THEN
        ALTER TABLE bundle.response_models
            ADD CONSTRAINT response_models_validation_methodology_check
            CHECK (
                validation_methodology IN (
                    'unspecified',
                    'holdout_validation',
                    'time_series_backtest',
                    'observational_statistical',
                    'quasi_experimental',
                    'randomized_experiment',
                    'econometric_causal'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'response_models_causal_evidence_level_check'
    ) THEN
        ALTER TABLE bundle.response_models
            ADD CONSTRAINT response_models_causal_evidence_level_check
            CHECK (
                causal_evidence_level IN (
                    'none',
                    'associational',
                    'quasi_experimental',
                    'experimental'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'response_models_drift_status_check'
    ) THEN
        ALTER TABLE bundle.response_models
            ADD CONSTRAINT response_models_drift_status_check
            CHECK (
                drift_status IN (
                    'not_checked',
                    'stable',
                    'warning',
                    'failed'
                )
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS response_models_governance_idx
ON bundle.response_models (
    validation_status,
    drift_status,
    expires_at,
    validated_at
);

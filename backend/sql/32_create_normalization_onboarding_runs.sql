BEGIN;

CREATE TABLE IF NOT EXISTS bundle.normalization_onboarding_runs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    filename TEXT NOT NULL,

    onboarding_version TEXT NOT NULL,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'passed',
                'failed'
            )
        ),

    summary_json JSONB NOT NULL,

    checks_json JSONB NOT NULL,

    result_json JSONB NOT NULL,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_onboarding_runs_dataset
ON bundle.normalization_onboarding_runs (
    dataset_name,
    created_at DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_onboarding_runs_status
ON bundle.normalization_onboarding_runs (
    status,
    created_at DESC
);

COMMIT;

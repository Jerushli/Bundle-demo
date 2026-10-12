BEGIN;

CREATE TABLE IF NOT EXISTS bundle.intelligence_daily_briefs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    evidence_package_id BIGINT
        REFERENCES bundle.intelligence_evidence_packages(id)
        ON DELETE SET NULL,

    evidence_date DATE,

    role_name TEXT NOT NULL
        CHECK (
            role_name IN (
                'admin',
                'analyst',
                'viewer'
            )
        ),

    brief_version TEXT NOT NULL,

    executive_summary TEXT NOT NULL,

    markdown TEXT NOT NULL,

    llm_used BOOLEAN NOT NULL DEFAULT FALSE,

    llm_validation_status TEXT NOT NULL,

    llm_validation_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_daily_briefs_dataset_date
ON bundle.intelligence_daily_briefs (
    dataset_name,
    evidence_date DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_daily_briefs_role
ON bundle.intelligence_daily_briefs (
    role_name,
    id DESC
);

COMMIT;

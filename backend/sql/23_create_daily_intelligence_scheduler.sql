BEGIN;

CREATE TABLE IF NOT EXISTS bundle.intelligence_daily_runs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    run_date DATE NOT NULL,

    role_name TEXT NOT NULL
        CHECK (
            role_name IN (
                'admin',
                'analyst',
                'viewer'
            )
        ),

    status TEXT NOT NULL
        CHECK (
            status IN (
                'running',
                'completed',
                'failed'
            )
        ),

    snapshot_status TEXT,
    change_status TEXT,

    evidence_package_id BIGINT
        REFERENCES bundle.intelligence_evidence_packages(id)
        ON DELETE SET NULL,

    brief_id BIGINT
        REFERENCES bundle.intelligence_daily_briefs(id)
        ON DELETE SET NULL,

    alert_count INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    error_message TEXT
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_daily_runs_dataset_date
ON bundle.intelligence_daily_runs (
    dataset_name,
    run_date DESC,
    id DESC
);


CREATE TABLE IF NOT EXISTS bundle.intelligence_alerts (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    run_id BIGINT
        REFERENCES bundle.intelligence_daily_runs(id)
        ON DELETE SET NULL,

    role_name TEXT NOT NULL
        CHECK (
            role_name IN (
                'admin',
                'analyst',
                'viewer'
            )
        ),

    alert_type TEXT NOT NULL,
    alert_key TEXT NOT NULL,

    severity TEXT NOT NULL
        CHECK (
            severity IN (
                'warning',
                'critical'
            )
        ),

    title TEXT NOT NULL,
    message TEXT NOT NULL,

    evidence_date DATE,

    evidence_payload JSONB NOT NULL,

    fingerprint TEXT NOT NULL UNIQUE,

    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_alerts_dataset_open
ON bundle.intelligence_alerts (
    dataset_name,
    role_name,
    acknowledged,
    created_at DESC
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_alerts_severity
ON bundle.intelligence_alerts (
    dataset_name,
    severity,
    created_at DESC
);

COMMIT;

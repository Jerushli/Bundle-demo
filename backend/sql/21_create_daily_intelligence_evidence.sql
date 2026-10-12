BEGIN;

CREATE TABLE IF NOT EXISTS bundle.intelligence_evidence_packages (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    evidence_date DATE,
    role_name TEXT NOT NULL
        CHECK (role_name IN ('admin', 'analyst', 'viewer')),
    evidence_version TEXT NOT NULL,
    evidence_json JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intelligence_evidence_dataset_date
ON bundle.intelligence_evidence_packages (
    dataset_name,
    evidence_date DESC,
    id DESC
);

CREATE INDEX IF NOT EXISTS idx_intelligence_evidence_role
ON bundle.intelligence_evidence_packages (
    dataset_name,
    role_name,
    id DESC
);

COMMIT;

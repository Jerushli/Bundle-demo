CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.validation_reports (
    id BIGSERIAL PRIMARY KEY,
    dataset_name VARCHAR(100) NOT NULL,
    staging_table VARCHAR(100) NOT NULL,
    validation_mode VARCHAR(50) NOT NULL,
    ready_for_transform BOOLEAN NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS validation_reports_dataset_idx
ON staging.validation_reports (
    dataset_name,
    created_at DESC
);

CREATE INDEX IF NOT EXISTS validation_reports_ready_idx
ON staging.validation_reports (
    ready_for_transform,
    created_at DESC
);

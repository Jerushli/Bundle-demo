CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    dataset_name VARCHAR(100) NOT NULL,
    staging_table VARCHAR(100) NOT NULL,
    dataset_fingerprint CHAR(64) NOT NULL,
    files_total INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL
        CHECK (
            status IN ('running', 'completed', 'failed')
        ),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingestion_jobs_dataset_name_idx
ON staging.ingestion_jobs (dataset_name);

CREATE INDEX IF NOT EXISTS ingestion_jobs_status_idx
ON staging.ingestion_jobs (status);

CREATE INDEX IF NOT EXISTS ingestion_jobs_started_at_idx
ON staging.ingestion_jobs (started_at DESC);

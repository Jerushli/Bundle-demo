CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.transformation_jobs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    source_table VARCHAR(150) NOT NULL,

    target_table VARCHAR(150) NOT NULL,

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'running',
                'completed',
                'failed'
            )
        ),

    rows_transformed BIGINT NOT NULL
        DEFAULT 0,

    rows_quarantined BIGINT NOT NULL
        DEFAULT 0,

    error_message TEXT,

    started_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    finished_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.quarantined_rows (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    source_table VARCHAR(150) NOT NULL,

    source_file TEXT,

    source_row BIGINT,

    raw_record JSONB NOT NULL,

    reason TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
    transformation_jobs_dataset_idx
ON staging.transformation_jobs (
    dataset_name,
    started_at DESC
);

CREATE INDEX IF NOT EXISTS
    quarantined_rows_dataset_idx
ON staging.quarantined_rows (
    dataset_name,
    created_at DESC
);

CREATE INDEX IF NOT EXISTS
    quarantined_rows_source_idx
ON staging.quarantined_rows (
    source_file,
    source_row
);

CREATE SCHEMA IF NOT EXISTS bundle;

CREATE TABLE IF NOT EXISTS bundle.pipeline_jobs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    original_filename TEXT NOT NULL,

    uploaded_path TEXT,

    status VARCHAR(40) NOT NULL
        CHECK (
            status IN (
                'queued',
                'uploading',
                'ingesting',
                'profiling',
                'validating',
                'transforming',
                'business_profiling',
                'ready',
                'failed'
            )
        ),

    current_stage VARCHAR(40) NOT NULL,

    rows_loaded BIGINT,

    rows_transformed BIGINT,

    rows_quarantined BIGINT,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    started_at TIMESTAMPTZ,

    finished_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
    pipeline_jobs_dataset_idx
ON bundle.pipeline_jobs (
    dataset_name,
    id DESC
);

CREATE INDEX IF NOT EXISTS
    pipeline_jobs_status_idx
ON bundle.pipeline_jobs (
    status,
    id DESC
);

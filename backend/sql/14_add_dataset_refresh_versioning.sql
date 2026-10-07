-- Bundle v2 Stage 12.3
-- Safe refresh/version tracking.

ALTER TABLE bundle.pipeline_jobs
    ADD COLUMN IF NOT EXISTS
        job_type VARCHAR(20) NOT NULL
        DEFAULT 'create';

ALTER TABLE bundle.pipeline_jobs
    ADD COLUMN IF NOT EXISTS
        technical_dataset_name VARCHAR(100);

ALTER TABLE bundle.pipeline_jobs
    DROP CONSTRAINT IF EXISTS
        pipeline_jobs_status_check;

ALTER TABLE bundle.pipeline_jobs
    ADD CONSTRAINT
        pipeline_jobs_status_check
    CHECK (
        status IN (
            'queued',
            'uploading',
            'ingesting',
            'profiling',
            'validating',
            'quality_check',
            'transforming',
            'business_profiling',
            'promoting',
            'ready',
            'failed'
        )
    );

ALTER TABLE bundle.pipeline_jobs
    DROP CONSTRAINT IF EXISTS
        pipeline_jobs_job_type_check;

ALTER TABLE bundle.pipeline_jobs
    ADD CONSTRAINT
        pipeline_jobs_job_type_check
    CHECK (
        job_type IN (
            'create',
            'refresh'
        )
    );

CREATE TABLE IF NOT EXISTS
    bundle.dataset_versions
(
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    refresh_job_id BIGINT NOT NULL
        REFERENCES bundle.pipeline_jobs(id),

    source_name TEXT,

    live_table VARCHAR(200) NOT NULL,

    archived_table VARCHAR(200) NOT NULL,

    row_count BIGINT NOT NULL,

    promoted_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    UNIQUE (
        dataset_name,
        refresh_job_id
    )
);

CREATE INDEX IF NOT EXISTS
    dataset_versions_dataset_idx
ON bundle.dataset_versions (
    dataset_name,
    promoted_at DESC
);

CREATE INDEX IF NOT EXISTS
    pipeline_jobs_job_type_idx
ON bundle.pipeline_jobs (
    job_type,
    id DESC
);


BEGIN;

CREATE TABLE IF NOT EXISTS bundle.massive_data_stream_loads (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    analytics_schema TEXT NOT NULL,
    analytics_table TEXT NOT NULL,
    detected_analytics_columns JSONB NOT NULL,
    inserted_rows BIGINT NOT NULL,
    rejected_rows BIGINT NOT NULL,
    batch_size INTEGER NOT NULL,
    batch_count INTEGER NOT NULL,
    duration_seconds NUMERIC NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('completed','completed_with_rejections','failed')
    ),
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_massive_data_stream_loads_dataset
ON bundle.massive_data_stream_loads (dataset_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_massive_data_stream_loads_hash
ON bundle.massive_data_stream_loads (source_sha256);

COMMIT;

BEGIN;

ALTER TABLE bundle.normalization_rag_queue
    ADD COLUMN IF NOT EXISTS rag_document_id BIGINT;
ALTER TABLE bundle.normalization_rag_queue
    ADD COLUMN IF NOT EXISTS rag_access_level_confirmed TEXT;
ALTER TABLE bundle.normalization_rag_queue
    ADD COLUMN IF NOT EXISTS reconciled_by TEXT;
ALTER TABLE bundle.normalization_rag_queue
    ADD COLUMN IF NOT EXISTS reconciled_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS bundle.normalization_lineage (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_row_number INTEGER,
    source_column TEXT,
    target_system TEXT NOT NULL
        CHECK (target_system IN ('analytics','rag')),
    target_locator TEXT NOT NULL,
    target_record_key TEXT NOT NULL,
    lineage_status TEXT NOT NULL
        CHECK (lineage_status IN ('pending','confirmed','failed')),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        dataset_name,
        source_sha256,
        source_row_number,
        source_column,
        target_system,
        target_record_key
    )
);

CREATE INDEX IF NOT EXISTS idx_normalization_lineage_source
ON bundle.normalization_lineage (
    dataset_name,
    source_row_number,
    source_column
);

CREATE INDEX IF NOT EXISTS idx_normalization_lineage_hash
ON bundle.normalization_lineage (
    source_sha256,
    source_row_number
);

CREATE INDEX IF NOT EXISTS idx_normalization_lineage_target
ON bundle.normalization_lineage (
    target_system,
    target_locator,
    target_record_key
);

COMMIT;

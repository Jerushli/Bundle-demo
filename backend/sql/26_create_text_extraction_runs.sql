BEGIN;

CREATE TABLE IF NOT EXISTS bundle.text_extraction_runs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT,

    analysis_id BIGINT
        REFERENCES bundle.input_column_analyses(id)
        ON DELETE SET NULL,

    filename TEXT NOT NULL,

    file_sha256 TEXT NOT NULL,

    extractor_version TEXT NOT NULL,

    selected_columns JSONB NOT NULL,

    attempted_text_cells INTEGER NOT NULL,

    successful_extractions INTEGER NOT NULL,

    extraction_success_ratio NUMERIC NOT NULL
        CHECK (
            extraction_success_ratio >= 0
            AND extraction_success_ratio <= 1
        ),

    candidate_record_count INTEGER NOT NULL,

    discovered_fields JSONB NOT NULL,

    result_json JSONB NOT NULL,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_text_extraction_runs_created
ON bundle.text_extraction_runs (
    created_at DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_text_extraction_runs_dataset
ON bundle.text_extraction_runs (
    dataset_name,
    created_at DESC
);

COMMIT;

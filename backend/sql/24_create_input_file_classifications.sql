
BEGIN;

CREATE TABLE IF NOT EXISTS bundle.input_file_classifications (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT,
    filename TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    classifier_version TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (
        classification IN ('structured','mixed','unstructured','invalid')
    ),
    confidence NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    recommended_route TEXT NOT NULL CHECK (
        recommended_route IN (
            'existing_structured_pipeline',
            'mixed_content_analysis',
            'text_extraction_required',
            'reject_or_review'
        )
    ),
    sampled_rows INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    result_json JSONB NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_input_file_classifications_created
ON bundle.input_file_classifications (created_at DESC,id DESC);

COMMIT;

BEGIN;
CREATE TABLE IF NOT EXISTS bundle.input_column_analyses (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT,
    classification_id BIGINT REFERENCES bundle.input_file_classifications(id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    file_route TEXT NOT NULL CHECK (file_route IN (
        'structured_only','split_structured_and_rag','extract_embedded_structure_then_split','rag_only','human_review_before_routing'
    )),
    sampled_rows INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    analysis_json JSONB NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_input_column_analyses_created ON bundle.input_column_analyses(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_input_column_analyses_route ON bundle.input_column_analyses(file_route, created_at DESC);
COMMIT;

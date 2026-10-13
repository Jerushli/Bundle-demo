BEGIN;

-- Stage 22.8 originally assumed RAG document IDs were numeric.
-- Existing Bundle RAG uses identifier-style IDs too (DOC-..., NORM-...).
-- Preserve document identifiers exactly as TEXT.

ALTER TABLE bundle.normalization_rag_queue
    ADD COLUMN IF NOT EXISTS rag_document_id TEXT;

DO $$
DECLARE
    column_type TEXT;
BEGIN
    SELECT data_type
    INTO column_type
    FROM information_schema.columns
    WHERE
        table_schema = 'bundle'
        AND table_name = 'normalization_rag_queue'
        AND column_name = 'rag_document_id';

    IF column_type IS NOT NULL
       AND column_type <> 'text'
    THEN
        ALTER TABLE bundle.normalization_rag_queue
            ALTER COLUMN rag_document_id
            TYPE TEXT
            USING rag_document_id::TEXT;
    END IF;
END
$$;

COMMIT;

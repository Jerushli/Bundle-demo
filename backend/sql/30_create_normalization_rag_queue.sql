BEGIN;

CREATE TABLE IF NOT EXISTS bundle.normalization_rag_routes (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    source_filename TEXT NOT NULL,

    source_sha256 TEXT NOT NULL,

    routing_version TEXT NOT NULL,

    access_level TEXT NOT NULL
        CHECK (
            access_level IN (
                'public',
                'internal',
                'restricted'
            )
        ),

    selected_columns JSONB NOT NULL,

    candidate_count INTEGER NOT NULL,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'rag_candidates_ready',
                'no_rag_candidates'
            )
        ),

    result_json JSONB NOT NULL,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS bundle.normalization_rag_queue (
    id BIGSERIAL PRIMARY KEY,

    rag_route_id BIGINT NOT NULL
        REFERENCES bundle.normalization_rag_routes(id)
        ON DELETE CASCADE,

    candidate_key TEXT NOT NULL UNIQUE,

    dataset_name TEXT NOT NULL,

    source_filename TEXT NOT NULL,

    source_sha256 TEXT NOT NULL,

    source_row_number INTEGER NOT NULL,

    source_column TEXT NOT NULL,

    title TEXT NOT NULL,

    body TEXT NOT NULL,

    document_type TEXT NOT NULL,

    access_level TEXT NOT NULL
        CHECK (
            access_level IN (
                'public',
                'internal',
                'restricted'
            )
        ),

    queue_status TEXT NOT NULL
        CHECK (
            queue_status IN (
                'pending_export',
                'exported',
                'ingested',
                'failed'
            )
        ),

    export_batch_id TEXT,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_rag_queue_status
ON bundle.normalization_rag_queue (
    queue_status,
    id
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_rag_queue_dataset
ON bundle.normalization_rag_queue (
    dataset_name,
    source_row_number,
    source_column
);

COMMIT;

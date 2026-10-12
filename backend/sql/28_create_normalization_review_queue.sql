BEGIN;

CREATE TABLE IF NOT EXISTS bundle.normalization_review_batches (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT,

    validation_run_id BIGINT
        REFERENCES bundle.extraction_validation_runs(id)
        ON DELETE SET NULL,

    filename TEXT NOT NULL,

    review_version TEXT NOT NULL,

    eligible_for_routing_count INTEGER NOT NULL,

    human_review_count INTEGER NOT NULL,

    blocked_count INTEGER NOT NULL,

    result_json JSONB NOT NULL,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS bundle.normalization_review_queue (
    id BIGSERIAL PRIMARY KEY,

    review_batch_id BIGINT NOT NULL
        REFERENCES bundle.normalization_review_batches(id)
        ON DELETE CASCADE,

    dataset_name TEXT,

    source_row_number INTEGER,

    source_column TEXT,

    raw_text TEXT,

    candidate_fields JSONB NOT NULL,

    normalized_fields JSONB NOT NULL,

    validation_warnings JSONB NOT NULL,

    validation_errors JSONB NOT NULL,

    confidence NUMERIC NOT NULL
        CHECK (
            confidence >= 0
            AND confidence <= 1
        ),

    confidence_band TEXT NOT NULL
        CHECK (
            confidence_band IN (
                'high',
                'medium',
                'low'
            )
        ),

    review_status TEXT NOT NULL
        CHECK (
            review_status IN (
                'pending',
                'approved',
                'rejected'
            )
        ),

    reviewed_by TEXT,

    reviewed_at TIMESTAMPTZ,

    reviewer_note TEXT,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_review_queue_status
ON bundle.normalization_review_queue (
    review_status,
    created_at DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_review_queue_batch
ON bundle.normalization_review_queue (
    review_batch_id,
    id
);

COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS bundle.extraction_validation_runs (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT,

    extraction_run_id BIGINT
        REFERENCES bundle.text_extraction_runs(id)
        ON DELETE SET NULL,

    filename TEXT NOT NULL,

    validator_version TEXT NOT NULL,

    candidate_record_count INTEGER NOT NULL,

    accepted_count INTEGER NOT NULL,

    needs_review_count INTEGER NOT NULL,

    rejected_count INTEGER NOT NULL,

    accepted_ratio NUMERIC NOT NULL
        CHECK (
            accepted_ratio >= 0
            AND accepted_ratio <= 1
        ),

    overall_status TEXT NOT NULL
        CHECK (
            overall_status IN (
                'ready_for_routing',
                'ready_for_review',
                'partially_valid',
                'invalid'
            )
        ),

    result_json JSONB NOT NULL,

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_extraction_validation_runs_created
ON bundle.extraction_validation_runs (
    created_at DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_extraction_validation_runs_status
ON bundle.extraction_validation_runs (
    overall_status,
    created_at DESC
);

COMMIT;

BEGIN;

CREATE TABLE IF NOT EXISTS bundle.normalization_structured_routes (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    source_filename TEXT NOT NULL,

    source_sha256 TEXT NOT NULL,

    routing_version TEXT NOT NULL,

    analytics_schema TEXT NOT NULL,

    analytics_table TEXT NOT NULL,

    routed_count INTEGER NOT NULL,

    blocked_count INTEGER NOT NULL,

    column_types JSONB NOT NULL,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'ready_for_onboarding',
                'superseded'
            )
        ),

    created_by TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_structured_routes_dataset
ON bundle.normalization_structured_routes (
    dataset_name,
    created_at DESC,
    id DESC
);


CREATE INDEX IF NOT EXISTS
    idx_normalization_structured_routes_hash
ON bundle.normalization_structured_routes (
    source_sha256,
    id DESC
);

COMMIT;

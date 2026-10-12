BEGIN;

CREATE SCHEMA IF NOT EXISTS bundle;

CREATE TABLE IF NOT EXISTS bundle.intelligence_kpi_definitions (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    kpi_key TEXT NOT NULL,
    display_name TEXT NOT NULL,

    column_name TEXT NOT NULL,

    aggregation TEXT NOT NULL
        CHECK (
            aggregation IN (
                'sum',
                'avg',
                'count',
                'min',
                'max'
            )
        ),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_intelligence_kpi_dataset_key
        UNIQUE (dataset_name, kpi_key)
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_kpi_definitions_dataset_enabled
ON bundle.intelligence_kpi_definitions (
    dataset_name,
    enabled
);


CREATE TABLE IF NOT EXISTS bundle.intelligence_kpi_snapshots (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    kpi_definition_id BIGINT NOT NULL
        REFERENCES bundle.intelligence_kpi_definitions(id)
        ON DELETE CASCADE,

    snapshot_date DATE NOT NULL,

    metric_value NUMERIC,
    row_count BIGINT,

    status TEXT NOT NULL
        CHECK (
            status IN (
                'success',
                'failed'
            )
        ),

    error_message TEXT,

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_intelligence_kpi_snapshot_day
        UNIQUE (
            kpi_definition_id,
            snapshot_date
        )
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_kpi_snapshots_dataset_date
ON bundle.intelligence_kpi_snapshots (
    dataset_name,
    snapshot_date DESC
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_kpi_snapshots_kpi_date
ON bundle.intelligence_kpi_snapshots (
    kpi_definition_id,
    snapshot_date DESC
);

COMMIT;

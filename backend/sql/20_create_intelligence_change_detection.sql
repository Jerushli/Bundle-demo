BEGIN;

CREATE TABLE IF NOT EXISTS bundle.intelligence_change_rules (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    kpi_definition_id BIGINT NOT NULL
        REFERENCES bundle.intelligence_kpi_definitions(id)
        ON DELETE CASCADE,

    warning_change_percent NUMERIC NOT NULL
        CHECK (warning_change_percent >= 0),

    critical_change_percent NUMERIC NOT NULL
        CHECK (
            critical_change_percent > 0
            AND critical_change_percent >= warning_change_percent
        ),

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_intelligence_change_rule
        UNIQUE (
            dataset_name,
            kpi_definition_id
        )
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_change_rules_dataset_enabled
ON bundle.intelligence_change_rules (
    dataset_name,
    enabled
);


CREATE TABLE IF NOT EXISTS bundle.intelligence_change_events (
    id BIGSERIAL PRIMARY KEY,

    dataset_name TEXT NOT NULL,

    kpi_definition_id BIGINT NOT NULL
        REFERENCES bundle.intelligence_kpi_definitions(id)
        ON DELETE CASCADE,

    previous_snapshot_id BIGINT NOT NULL
        REFERENCES bundle.intelligence_kpi_snapshots(id)
        ON DELETE CASCADE,

    current_snapshot_id BIGINT NOT NULL
        REFERENCES bundle.intelligence_kpi_snapshots(id)
        ON DELETE CASCADE,

    previous_snapshot_date DATE NOT NULL,
    current_snapshot_date DATE NOT NULL,

    previous_value NUMERIC NOT NULL,
    current_value NUMERIC NOT NULL,

    absolute_change NUMERIC NOT NULL,
    percentage_change NUMERIC,

    direction TEXT NOT NULL
        CHECK (
            direction IN (
                'increase',
                'decrease',
                'stable'
            )
        ),

    severity TEXT NOT NULL
        CHECK (
            severity IN (
                'normal',
                'warning',
                'critical',
                'unclassified'
            )
        ),

    classification_reason TEXT NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_intelligence_change_event
        UNIQUE (
            dataset_name,
            kpi_definition_id,
            current_snapshot_id
        )
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_change_events_dataset_date
ON bundle.intelligence_change_events (
    dataset_name,
    current_snapshot_date DESC
);


CREATE INDEX IF NOT EXISTS
    idx_intelligence_change_events_severity
ON bundle.intelligence_change_events (
    dataset_name,
    severity,
    current_snapshot_date DESC
);

COMMIT;

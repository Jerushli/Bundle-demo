BEGIN;

CREATE TABLE IF NOT EXISTS bundle.dataset_schema_contracts (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft','approved','superseded')),
    sample_record_count INTEGER NOT NULL,
    field_count INTEGER NOT NULL,
    proposal_json JSONB NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by TEXT,
    approved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS bundle.dataset_schema_contract_fields (
    id BIGSERIAL PRIMARY KEY,
    contract_id BIGINT NOT NULL
        REFERENCES bundle.dataset_schema_contracts(id)
        ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    data_type TEXT NOT NULL
        CHECK (data_type IN ('date','integer','decimal','boolean','categorical','short_text','text')),
    required BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_values JSONB,
    max_length INTEGER,
    observed_min NUMERIC,
    observed_max NUMERIC,
    presence_ratio NUMERIC NOT NULL,
    distinct_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contract_id, field_name)
);

CREATE INDEX IF NOT EXISTS idx_dataset_schema_contracts_dataset
ON bundle.dataset_schema_contracts (dataset_name, status, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_schema_contract_approved
ON bundle.dataset_schema_contracts (dataset_name)
WHERE status = 'approved';

CREATE INDEX IF NOT EXISTS idx_dataset_schema_fields_contract
ON bundle.dataset_schema_contract_fields (contract_id, field_name);

COMMIT;

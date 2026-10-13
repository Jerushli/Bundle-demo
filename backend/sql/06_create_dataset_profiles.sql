CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.dataset_profiles (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    staging_table VARCHAR(100) NOT NULL,

    total_rows BIGINT NOT NULL,

    sample_rows BIGINT NOT NULL,

    column_count INTEGER NOT NULL,

    profile_json JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
    dataset_profiles_dataset_name_idx
ON staging.dataset_profiles (
    dataset_name,
    created_at DESC
);

CREATE INDEX IF NOT EXISTS
    dataset_profiles_created_at_idx
ON staging.dataset_profiles (
    created_at DESC
);

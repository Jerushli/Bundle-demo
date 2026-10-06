CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.dataset_business_profiles (
    id BIGSERIAL PRIMARY KEY,

    dataset_name VARCHAR(100) NOT NULL,

    analytics_table VARCHAR(150) NOT NULL,

    total_rows BIGINT NOT NULL,

    primary_measure VARCHAR(100),

    quick_summary TEXT NOT NULL,

    profile_json JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
    dataset_business_profiles_dataset_idx
ON analytics.dataset_business_profiles (
    dataset_name,
    created_at DESC
);

CREATE INDEX IF NOT EXISTS
    dataset_business_profiles_created_at_idx
ON analytics.dataset_business_profiles (
    created_at DESC
);

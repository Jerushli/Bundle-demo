CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.users (
    id BIGSERIAL PRIMARY KEY,

    username VARCHAR(100) NOT NULL,

    password_hash TEXT NOT NULL,

    role VARCHAR(20) NOT NULL
        CHECK (
            role IN (
                'admin',
                'analyst',
                'viewer'
            )
        ),

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS
    app_users_username_ci
ON app.users (
    lower(username)
);

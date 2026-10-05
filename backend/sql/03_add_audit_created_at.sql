ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS created_at
TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS
    audit_logs_created_at_idx
ON audit_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS
    audit_logs_username_idx
ON audit_logs (username);

CREATE INDEX IF NOT EXISTS
    audit_logs_status_idx
ON audit_logs (status);

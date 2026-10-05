ALTER TABLE app.users
ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1;

UPDATE app.users
SET token_version = 1
WHERE token_version IS NULL;

ALTER TABLE app.users
ALTER COLUMN token_version SET DEFAULT 1;

ALTER TABLE app.users
ALTER COLUMN token_version SET NOT NULL;

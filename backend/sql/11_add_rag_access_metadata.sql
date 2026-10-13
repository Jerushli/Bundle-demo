CREATE SCHEMA IF NOT EXISTS rag;

ALTER TABLE rag.documents
ADD COLUMN IF NOT EXISTS dataset_name VARCHAR(100);

ALTER TABLE rag.documents
ADD COLUMN IF NOT EXISTS department VARCHAR(100);

ALTER TABLE rag.documents
ADD COLUMN IF NOT EXISTS allowed_roles TEXT[];

UPDATE rag.documents
SET dataset_name = 'bundle_test_sales'
WHERE dataset_name IS NULL
  AND access_level = 'public';

UPDATE rag.documents
SET allowed_roles = ARRAY['admin','analyst','viewer']::TEXT[]
WHERE access_level = 'public'
  AND allowed_roles IS NULL;

UPDATE rag.documents
SET allowed_roles = ARRAY['admin','analyst']::TEXT[]
WHERE access_level = 'internal'
  AND allowed_roles IS NULL;

UPDATE rag.documents
SET allowed_roles = ARRAY['admin']::TEXT[]
WHERE access_level = 'restricted'
  AND allowed_roles IS NULL;

CREATE INDEX IF NOT EXISTS rag_documents_dataset_idx
ON rag.documents (dataset_name);

CREATE INDEX IF NOT EXISTS rag_documents_access_idx
ON rag.documents (dataset_name, access_level);

CREATE INDEX IF NOT EXISTS rag_documents_allowed_roles_gin_idx
ON rag.documents
USING GIN (allowed_roles);

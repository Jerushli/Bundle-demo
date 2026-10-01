-- Run against bundle_rag_test in pgAdmin, as the DB owner/admin.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS rag.document_embeddings (
  document_id TEXT PRIMARY KEY REFERENCES rag.documents(id) ON DELETE CASCADE,
  model_name TEXT NOT NULL,
  embedding vector(384) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rag_document_embeddings_model_idx ON rag.document_embeddings(model_name);
-- For an initial 200-row experiment a sequential similarity scan is sufficient.
-- Do not add an ANN index until recall and access filtering have been validated.

-- Run in the database dedicated to the fictional COMPANY dataset.
-- SQL-only lexical retrieval starter; NOT yet semantic vector RAG.
CREATE SCHEMA IF NOT EXISTS rag;
CREATE TABLE IF NOT EXISTS rag.documents (
  id text PRIMARY KEY,
  title text NOT NULL,
  document_type text NOT NULL,
  doc_date date NOT NULL,
  department text NOT NULL,
  country text NOT NULL,
  priority text NOT NULL,
  status text NOT NULL,
  access_level text NOT NULL CHECK (access_level IN ('public','internal','restricted')),
  project_id text NOT NULL,
  customer_id text NOT NULL,
  employee_id text NOT NULL,
  control_id text NOT NULL,
  body text NOT NULL,
  search_vector tsvector GENERATED ALWAYS AS
    (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,''))) STORED
);
CREATE INDEX IF NOT EXISTS rag_documents_search_idx ON rag.documents USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS rag_documents_access_idx ON rag.documents(access_level);
CREATE INDEX IF NOT EXISTS rag_documents_department_date_idx ON rag.documents(department,doc_date);
-- Do not grant unrestricted SELECT to end users: enforce access rules in your backend.

from __future__ import annotations

import os
import psycopg
from pgvector.psycopg import register_vector


def get_rag_database_url() -> str:
    url = os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("RAG_DATABASE_URL (or DATABASE_URL) is missing.")
    return url.strip()


def get_rag_connection():
    connection = psycopg.connect(get_rag_database_url())
    register_vector(connection)
    return connection

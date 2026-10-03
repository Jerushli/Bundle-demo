
"""Public-only semantic nearest-neighbor preview using FastEmbed."""

import os
import sys

import numpy as np
import psycopg

from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DATABASE_MODEL_NAME = MODEL_NAME


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            'Usage: python rag_test/04_search_sample.py "your question"'
        )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise SystemExit(
            "DATABASE_URL missing in PowerShell session"
        )

    question = " ".join(sys.argv[1:]).strip()

    if not question:
        raise SystemExit("Question cannot be empty")

    print(f"Query: {question}")
    print("Loading FastEmbed model...", flush=True)

    model = TextEmbedding(model_name=MODEL_NAME)

    # FastEmbed returns a NumPy embedding.
    # Keep it as a NumPy float32 array for pgvector's
    # registered Psycopg adapter.
    query_vectors = list(model.query_embed(question))

    if not query_vectors:
        raise SystemExit(
            "Embedding model returned no query vector"
        )

    vector = np.asarray(
        query_vectors[0],
        dtype=np.float32
    )

    if vector.ndim != 1 or vector.size != 384:
        raise SystemExit(
            f"Unexpected embedding dimensions: {vector.shape}"
        )

    with psycopg.connect(database_url) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.document_type,
                    d.access_level,
                    e.embedding <=> %s::vector
                        AS cosine_distance
                FROM rag.document_embeddings e
                JOIN rag.documents d
                    ON d.id = e.document_id
                WHERE
                    d.access_level = 'public'
                    AND e.model_name = %s
                ORDER BY
                    e.embedding <=> %s::vector
                LIMIT 5
                """,
                (
                    vector,
                    DATABASE_MODEL_NAME,
                    vector,
                ),
            )

            results = cur.fetchall()

    if not results:
        print(
            "No eligible embedded public documents. "
            "Check the stored model_name and run "
            "03_embed_sample.py if needed."
        )
        return

    print("\nTop semantic matches:\n")

    for (
        doc_id,
        title,
        document_type,
        access_level,
        distance,
    ) in results:
        similarity = 1 - float(distance)

        print(
            f"{doc_id}"
            f" | {title}"
            f" | {document_type}"
            f" | access={access_level}"
            f" | distance={float(distance):.4f}"
            f" | similarity={similarity:.4f}"
        )


if __name__ == "__main__":
    main()

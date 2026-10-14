"""Embed eligible RAG documents using the existing FastEmbed model."""

import argparse
import os

import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dataset", default="bundle_test_sales")
    parser.add_argument(
        "--access-level",
        choices=["public", "internal", "restricted"],
        default="public",
    )
    args = parser.parse_args()

    if not 1 <= args.limit <= 10000:
        raise SystemExit("--limit must be between 1 and 10000")

    database_url = os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("RAG_DATABASE_URL or DATABASE_URL is missing")

    model = TextEmbedding(model_name=MODEL_NAME)

    with psycopg.connect(database_url) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.title, d.body
                FROM rag.documents d
                WHERE
                    d.dataset_name = %s
                    AND d.access_level = %s
                    AND NOT EXISTS (
                        SELECT 1
                        FROM rag.document_embeddings e
                        WHERE e.document_id = d.id
                          AND e.model_name = %s
                    )
                ORDER BY d.id
                LIMIT %s
                """,
                (
                    args.dataset,
                    args.access_level,
                    MODEL_NAME,
                    args.limit,
                ),
            )
            docs = cur.fetchall()

            print(
                f"Embedding {len(docs)} {args.access_level.upper()} "
                f"document(s) for dataset {args.dataset}."
            )

            batch_size = 16

            for start in range(0, len(docs), batch_size):
                batch = docs[start:start + batch_size]

                texts = [
                    f"{title}. {body}"
                    for _, title, body in batch
                ]

                vectors = list(
                    model.embed(
                        texts,
                        batch_size=batch_size,
                    )
                )

                rows_to_insert = [
                    (doc_id, MODEL_NAME, vector.tolist())
                    for (doc_id, _, _), vector in zip(batch, vectors)
                ]

                cur.executemany(
                    """
                    INSERT INTO rag.document_embeddings
                    (
                        document_id,
                        model_name,
                        embedding
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        model_name = EXCLUDED.model_name,
                        embedding = EXCLUDED.embedding,
                        created_at = now()
                    """,
                    rows_to_insert,
                )

                conn.commit()

                print(
                    f"Inserted "
                    f"{min(start + batch_size, len(docs))}"
                    f"/{len(docs)}"
                )

    print("Done.")


if __name__ == "__main__":
    main()

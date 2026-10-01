"""Embed a small subset of public synthetic documents using FastEmbed."""

import os
import argparse

import psycopg

from fastembed import TextEmbedding
from pgvector.psycopg import register_vector


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=200,
    )

    args = parser.parse_args()

    if not 1 <= args.limit <= 10000:
        raise SystemExit(
            "--limit must be between 1 and 10000 "
            "for this initial test"
        )

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise SystemExit(
            "DATABASE_URL is missing in this PowerShell session"
        )

    print("Loading FastEmbed model...")

    model = TextEmbedding(
        model_name=MODEL_NAME
    )

    print("Embedding model ready.")

    with psycopg.connect(database_url) as conn:

        register_vector(conn)

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.body

                FROM rag.documents d

                WHERE
                    d.access_level = 'public'

                    AND NOT EXISTS (
                        SELECT 1
                        FROM rag.document_embeddings e
                        WHERE
                            e.document_id = d.id
                            AND e.model_name = %s
                    )

                ORDER BY d.id

                LIMIT %s
                """,
                (
                    MODEL_NAME,
                    args.limit,
                ),
            )

            docs = cur.fetchall()

            print(
                f"Embedding {len(docs)} PUBLIC documents "
                f"(source documents stay unchanged)."
            )

            batch_size = 16

            for start in range(
                0,
                len(docs),
                batch_size,
            ):

                batch = docs[
                    start:
                    start + batch_size
                ]

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

                rows_to_insert = []

                for (
                    doc_id,
                    _,
                    _
                ), vector in zip(
                    batch,
                    vectors,
                ):

                    rows_to_insert.append(
                        (
                            doc_id,
                            MODEL_NAME,
                            vector.tolist(),
                        )
                    )

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
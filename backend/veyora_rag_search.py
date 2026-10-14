
from __future__ import annotations

import argparse
import json
import os
import re

import numpy as np
import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ALLOWED_ROLES = {"admin", "analyst", "viewer"}
KNOWN_REGIONS = ("North", "South", "East", "West")
DEFAULT_MINIMUM_SIMILARITY = 0.20


def detect_region(question: str) -> str | None:
    for region in KNOWN_REGIONS:
        if re.search(rf"\b{re.escape(region)}\b", question, re.IGNORECASE):
            return region
    return None


def search_veyora_rag(
    question: str,
    *,
    dataset_name: str = "veyora_massive",
    role: str = "analyst",
    limit: int = 5,
    minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
) -> dict:
    if role not in ALLOWED_ROLES:
        raise ValueError(f"Unsupported role: {role}")

    database_url = os.getenv("RAG_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "RAG_DATABASE_URL is required and must point to bundle_rag_test."
        )

    detected_region = detect_region(question)

    model = TextEmbedding(model_name=MODEL_NAME)
    vectors = list(model.query_embed(question))
    if not vectors:
        raise RuntimeError("Embedding model returned no query vector.")

    vector = np.asarray(vectors[0], dtype=np.float32)
    safe_limit = max(1, min(int(limit), 10))

    # IMPORTANT:
    # Region-scoped evidence produced by the hardened exporter starts with:
    #   Region: North
    #
    # For a region question we intentionally require that prefix.
    body_prefix = (
        f"Region: {detected_region}\n%"
        if detected_region
        else None
    )

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH eligible AS (
                    SELECT
                        d.id,
                        d.title,
                        d.body,
                        d.access_level,
                        e.embedding <=> %s::vector AS cosine_distance,
                        ROW_NUMBER() OVER (
                            PARTITION BY d.title, d.body
                            ORDER BY d.id DESC
                        ) AS duplicate_rank
                    FROM rag.document_embeddings e
                    JOIN rag.documents d
                      ON d.id = e.document_id
                    WHERE d.dataset_name = %s
                      AND %s = ANY(d.allowed_roles)
                      AND e.model_name = %s
                      AND (
                            %s::text IS NULL
                            OR d.body LIKE %s
                          )
                )
                SELECT
                    id,
                    title,
                    body,
                    access_level,
                    cosine_distance
                FROM eligible
                WHERE duplicate_rank = 1
                  AND (1.0 - cosine_distance) >= %s
                ORDER BY cosine_distance
                LIMIT %s
                """,
                (
                    vector,
                    dataset_name,
                    role,
                    MODEL_NAME,
                    detected_region,
                    body_prefix,
                    minimum_similarity,
                    safe_limit,
                ),
            )
            rows = cursor.fetchall()

    return {
        "dataset_name": dataset_name,
        "role": role,
        "question": question,
        "detected_region": detected_region,
        "minimum_similarity": minimum_similarity,
        "region_filter_applied": detected_region is not None,
        "duplicate_suppression_applied": True,
        "result_count": len(rows),
        "results": [
            {
                "document_id": str(row[0]),
                "title": str(row[1]),
                "body": str(row[2]),
                "access_level": str(row[3]),
                "cosine_distance": float(row[4]),
                "similarity": 1.0 - float(row[4]),
            }
            for row in rows
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--dataset-name", default="veyora_massive")
    parser.add_argument(
        "--role",
        default="analyst",
        choices=sorted(ALLOWED_ROLES),
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--minimum-similarity",
        type=float,
        default=DEFAULT_MINIMUM_SIMILARITY,
    )
    args = parser.parse_args()

    result = search_veyora_rag(
        args.question,
        dataset_name=args.dataset_name,
        role=args.role,
        limit=args.limit,
        minimum_similarity=args.minimum_similarity,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

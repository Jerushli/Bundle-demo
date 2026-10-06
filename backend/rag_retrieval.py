from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from fastembed import TextEmbedding

from backend.dataset_profiles import get_active_dataset_name
from backend.dataset_security import enforce_dataset_access, get_dataset_permission
from backend.rag_database import get_rag_connection


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
MAX_RAG_RESULTS = 8

ROLE_ACCESS_LEVELS = {
    "admin": ["public", "internal", "restricted"],
    "analyst": ["public", "internal"],
    "viewer": ["public"],
}


@dataclass(frozen=True)
class RAGResult:
    document_id: str
    title: str
    body: str
    document_type: str | None
    access_level: str
    dataset_name: str
    department: str | None
    similarity: float


_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def _embed_query(question: str) -> np.ndarray:
    vectors = list(_get_model().query_embed(question))
    if not vectors:
        raise ValueError("Embedding model returned no query vector.")

    vector = np.asarray(vectors[0], dtype=np.float32)
    if vector.ndim != 1 or vector.size != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Unexpected query embedding dimensions: {vector.shape}"
        )
    return vector


def retrieve_allowed_chunks(
    *,
    question: str,
    role: str,
    dataset_name: str | None = None,
    limit: int = 5,
    minimum_similarity: float = 0.25,
) -> list[RAGResult]:
    clean_dataset = dataset_name or get_active_dataset_name()

    permission = get_dataset_permission(
        dataset_name=clean_dataset,
        role=role,
    )
    enforce_dataset_access(permission=permission)

    allowed_access_levels = ROLE_ACCESS_LEVELS.get(role, [])
    if not allowed_access_levels:
        raise PermissionError(f"Role {role!r} has no RAG access levels.")

    safe_limit = max(
        1,
        min(int(limit), MAX_RAG_RESULTS, permission.max_result_rows),
    )

    vector = _embed_query(question)

    with get_rag_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.body,
                    d.document_type,
                    d.access_level,
                    d.dataset_name,
                    d.department,
                    1 - (e.embedding <=> %s::vector) AS similarity
                FROM rag.document_embeddings e
                JOIN rag.documents d
                    ON d.id = e.document_id
                WHERE
                    e.model_name = %s
                    AND d.dataset_name = %s
                    AND d.access_level = ANY(%s)
                    AND (
                        d.allowed_roles IS NULL
                        OR %s = ANY(d.allowed_roles)
                    )
                    AND (
                        1 - (e.embedding <=> %s::vector)
                    ) >= %s
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    vector,
                    MODEL_NAME,
                    clean_dataset,
                    allowed_access_levels,
                    role,
                    vector,
                    float(minimum_similarity),
                    vector,
                    safe_limit,
                ),
            )
            rows = cur.fetchall()

    return [
        RAGResult(
            document_id=str(row[0]),
            title=str(row[1] or ""),
            body=str(row[2] or ""),
            document_type=str(row[3]) if row[3] is not None else None,
            access_level=str(row[4]),
            dataset_name=str(row[5]),
            department=str(row[6]) if row[6] is not None else None,
            similarity=float(row[7]),
        )
        for row in rows
    ]


def rag_results_to_evidence(
    results: list[RAGResult],
) -> list[dict[str, Any]]:
    return [
        {
            "document_id": item.document_id,
            "title": item.title,
            "document_type": item.document_type,
            "access_level": item.access_level,
            "dataset_name": item.dataset_name,
            "department": item.department,
            "similarity": round(item.similarity, 4),
            "text": item.body,
        }
        for item in results
    ]

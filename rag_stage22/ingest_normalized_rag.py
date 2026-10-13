"""
Bundle Data Assistant
Stage 22.7 / Stage 22.9 RAG-side importer
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

ALLOWED_ACCESS_LEVELS = {
    "public",
    "internal",
    "restricted",
}

ACCESS_ROLE_MAP = {
    "public": ["admin", "analyst", "viewer"],
    "internal": ["admin", "analyst"],
    "restricted": ["admin"],
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Line {line_number}: invalid JSON."
                ) from exc

            access_level = payload.get("access_level")

            if access_level not in ALLOWED_ACCESS_LEVELS:
                raise ValueError(
                    f"Line {line_number}: access_level must be "
                    "public, internal, or restricted."
                )

            if not str(payload.get("body", "")).strip():
                raise ValueError(
                    f"Line {line_number}: body is empty."
                )

            if not str(payload.get("title", "")).strip():
                raise ValueError(
                    f"Line {line_number}: title is empty."
                )

            if not str(payload.get("candidate_key", "")).strip():
                raise ValueError(
                    f"Line {line_number}: candidate_key is missing."
                )

            rows.append(payload)

    return rows


def assert_rag_schema(connection) -> None:
    required_document_columns = {
        "id",
        "title",
        "document_type",
        "doc_date",
        "department",
        "country",
        "priority",
        "status",
        "access_level",
        "project_id",
        "customer_id",
        "employee_id",
        "control_id",
        "body",
        "dataset_name",
        "allowed_roles",
    }

    required_embedding_columns = {
        "document_id",
        "model_name",
        "embedding",
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                to_regclass('rag.documents'),
                to_regclass('rag.document_embeddings')
            """
        )

        documents_table, embeddings_table = cursor.fetchone()

        if documents_table is None:
            raise RuntimeError(
                "rag.documents does not exist in RAG_DATABASE_URL."
            )

        if embeddings_table is None:
            raise RuntimeError(
                "rag.document_embeddings does not exist in RAG_DATABASE_URL."
            )

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = 'rag'
                AND table_name = 'documents'
            """
        )
        actual_document_columns = {row[0] for row in cursor.fetchall()}

        missing_document_columns = (
            required_document_columns - actual_document_columns
        )

        if missing_document_columns:
            raise RuntimeError(
                "rag.documents is missing required columns: "
                + ", ".join(sorted(missing_document_columns))
            )

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = 'rag'
                AND table_name = 'document_embeddings'
            """
        )
        actual_embedding_columns = {row[0] for row in cursor.fetchall()}

        missing_embedding_columns = (
            required_embedding_columns - actual_embedding_columns
        )

        if missing_embedding_columns:
            raise RuntimeError(
                "rag.document_embeddings is missing required columns: "
                + ", ".join(sorted(missing_embedding_columns))
            )


def safe_token(
    value: Any,
    fallback: str,
    max_length: int = 80,
) -> str:
    text = str(value if value is not None else "").strip()

    if not text:
        text = fallback

    return text[:max_length]


def build_document_metadata(
    payload: dict[str, Any],
) -> dict[str, Any]:
    dataset_name = safe_token(
        payload.get("dataset_name"),
        "stage22_unknown_dataset",
        max_length=100,
    )

    source_row = payload.get("source_row_number")

    source_column = safe_token(
        payload.get("source_column"),
        "unknown_column",
    )

    candidate_key = safe_token(
        payload.get("candidate_key"),
        "missing_candidate",
        max_length=64,
    )

    access_level = str(payload["access_level"])

    suffix = candidate_key[:12].upper()

    return {
        "title": safe_token(
            payload.get("title"),
            (
                f"Bundle normalized context | "
                f"{dataset_name} | row {source_row}"
            ),
            max_length=500,
        ),
        "document_type": safe_token(
            payload.get("document_type"),
            "normalized_csv_context",
            max_length=100,
        ),
        # Stage 22.7 JSONL does not carry an authoritative business date,
        # so doc_date is the RAG ingestion date.
        "doc_date": date.today(),
        "department": "Analytics",
        "country": "India",
        "priority": "medium",
        "status": "in_progress",
        "access_level": access_level,

        # Required legacy RAG fields. These are explicit provenance placeholders,
        # not claims that the source row had real project/customer/employee IDs.
        "project_id": f"STAGE22-PROJECT-{suffix}",
        "customer_id": f"STAGE22-CUSTOMER-{suffix}",
        "employee_id": f"STAGE22-EMPLOYEE-{suffix}",
        "control_id": f"STAGE22-CONTROL-{suffix}",

        "body": str(payload["body"]).strip(),
        "dataset_name": dataset_name,
        "allowed_roles": ACCESS_ROLE_MAP[access_level],

        "source_row_number": source_row,
        "source_column": source_column,
        "candidate_key": candidate_key,
    }


def find_existing_document(
    cursor,
    metadata: dict[str, Any],
) -> str | None:
    cursor.execute(
        """
        SELECT id
        FROM rag.documents
        WHERE
            title = %s
            AND body = %s
            AND access_level = %s
            AND COALESCE(dataset_name, '') = %s
        ORDER BY id
        LIMIT 1
        """,
        (
            metadata["title"],
            metadata["body"],
            metadata["access_level"],
            metadata["dataset_name"],
        ),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return str(row[0])


def insert_document(
    cursor,
    metadata: dict[str, Any],
) -> str:
    cursor.execute(
        """
        INSERT INTO rag.documents (
            title,
            document_type,
            doc_date,
            department,
            country,
            priority,
            status,
            access_level,
            project_id,
            customer_id,
            employee_id,
            control_id,
            body,
            dataset_name,
            allowed_roles
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        RETURNING id
        """,
        (
            metadata["title"],
            metadata["document_type"],
            metadata["doc_date"],
            metadata["department"],
            metadata["country"],
            metadata["priority"],
            metadata["status"],
            metadata["access_level"],
            metadata["project_id"],
            metadata["customer_id"],
            metadata["employee_id"],
            metadata["control_id"],
            metadata["body"],
            metadata["dataset_name"],
            metadata["allowed_roles"],
        ),
    )

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "rag.documents INSERT did not return an id."
        )

    return str(row[0])


def upsert_embedding(
    cursor,
    *,
    document_id: str,
    vector: list[float],
) -> None:
    cursor.execute(
        """
        INSERT INTO rag.document_embeddings (
            document_id,
            model_name,
            embedding
        )
        VALUES (
            %s,
            %s,
            %s
        )
        ON CONFLICT (document_id)
        DO UPDATE SET
            model_name = EXCLUDED.model_name,
            embedding = EXCLUDED.embedding,
            created_at = NOW()
        """,
        (
            document_id,
            MODEL_NAME,
            vector,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest Stage 22 normalized narrative content into "
            "the existing secure Bundle RAG database."
        )
    )

    parser.add_argument("jsonl_path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    path = Path(args.jsonl_path)

    if not path.exists():
        raise SystemExit(
            f"JSONL file not found: {path}"
        )

    rows = load_rows(path)

    access_counts: dict[str, int] = {}

    for payload in rows:
        access = str(payload["access_level"])
        access_counts[access] = (
            access_counts.get(access, 0) + 1
        )

    print(
        f"Validated {len(rows)} Stage 22.7 RAG candidate(s)."
    )
    print(
        f"Access levels: {access_counts}"
    )

    if args.dry_run:
        print(
            "Dry run complete. No RAG database writes performed."
        )
        return

    database_url = os.getenv("RAG_DATABASE_URL")

    if not database_url:
        raise SystemExit(
            "RAG_DATABASE_URL is required. "
            "It must point to bundle_rag_test, not bundle_new."
        )

    print("Checking RAG schema...")

    mapping: list[dict[str, Any]] = []
    inserted_count = 0
    reused_count = 0

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        assert_rag_schema(connection)

        print("RAG schema verified.")
        print("Loading FastEmbed model...")

        model = TextEmbedding(
            model_name=MODEL_NAME
        )

        print("Embedding model ready.")

        with connection.cursor() as cursor:
            for index, payload in enumerate(
                rows,
                start=1,
            ):
                metadata = build_document_metadata(
                    payload
                )

                document_id = find_existing_document(
                    cursor,
                    metadata,
                )

                if document_id is None:
                    document_id = insert_document(
                        cursor,
                        metadata,
                    )
                    inserted_count += 1
                else:
                    reused_count += 1

                embedding_text = (
                    f"{metadata['title']}. "
                    f"{metadata['body']}"
                )

                vectors = list(
                    model.embed(
                        [embedding_text]
                    )
                )

                if not vectors:
                    raise RuntimeError(
                        "FastEmbed returned no embedding vector."
                    )

                vector = vectors[0].tolist()

                if len(vector) != 384:
                    raise RuntimeError(
                        "Unexpected embedding dimensions: "
                        f"{len(vector)}"
                    )

                upsert_embedding(
                    cursor,
                    document_id=document_id,
                    vector=vector,
                )

                mapping.append(
                    {
                        "queue_id": payload.get("queue_id"),
                        "candidate_key": metadata["candidate_key"],
                        "document_id": document_id,
                        "access_level": metadata["access_level"],
                        "dataset_name": metadata["dataset_name"],
                        "source_row_number": metadata["source_row_number"],
                        "source_column": metadata["source_column"],
                    }
                )

                print(
                    f"Processed {index}/{len(rows)} "
                    f"-> rag.documents.id={document_id}"
                )

        connection.commit()

    mapping_path = path.with_suffix(
        ".ingested.json"
    )

    mapping_path.write_text(
        json.dumps(
            {
                "model_name": MODEL_NAME,
                "source_jsonl": path.name,
                "ingested_count": len(mapping),
                "inserted_documents": inserted_count,
                "reused_documents": reused_count,
                "documents": mapping,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("")
    print(
        f"Ingested {len(mapping)} RAG document(s)."
    )
    print(
        f"New documents: {inserted_count}"
    )
    print(
        f"Existing documents reused: {reused_count}"
    )
    print(
        f"Model: {MODEL_NAME}"
    )
    print(
        f"Mapping written to: {mapping_path}"
    )
    print("")
    print(
        "Stage 22.7/22.9 RAG ingestion completed successfully."
    )


if __name__ == "__main__":
    main()

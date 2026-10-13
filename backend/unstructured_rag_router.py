from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.mixed_content_detector import analyze_csv_columns


ALLOWED_ACCESS_LEVELS = {
    "public",
    "internal",
    "restricted",
}


def collect_rag_candidates(
    file_path: str | Path,
    *,
    dataset_name: str,
    access_level: str = "internal",
    sample_rows: int = 5000,
    include_embedded_structure: bool = False,
) -> dict[str, Any]:
    if access_level not in ALLOWED_ACCESS_LEVELS:
        raise ValueError(
            "access_level must be public, internal, or restricted."
        )

    path = Path(
        file_path
    )

    if not path.exists():
        raise ValueError(
            f"File does not exist: {path}"
        )

    if path.suffix.lower() != ".csv":
        raise ValueError(
            "Stage 22.7 currently supports CSV files only."
        )

    raw = path.read_bytes()

    if not raw:
        raise ValueError(
            "CSV file is empty."
        )

    try:
        text = raw.decode(
            "utf-8-sig"
        )

    except UnicodeDecodeError as exc:
        raise ValueError(
            "CSV must currently be UTF-8 encoded."
        ) from exc

    analysis = analyze_csv_columns(
        path,
        sample_rows=min(
            sample_rows,
            5000,
        ),
    )

    allowed_semantic_types = {
        "free_text",
        "mixed",
    }

    if include_embedded_structure:
        allowed_semantic_types.add(
            "embedded_structure"
        )

    selected_columns = [
        item[
            "column_name"
        ]
        for item in analysis[
            "columns"
        ]
        if (
            item.get(
                "rag_candidate"
            )
            and item.get(
                "semantic_type"
            )
            in allowed_semantic_types
        )
    ]

    if not selected_columns:
        return {
            "source": "unstructured_rag_routing",
            "routing_version": "22.7",
            "dataset_name": dataset_name,
            "filename": path.name,
            "source_sha256": hashlib.sha256(
                raw
            ).hexdigest(),
            "access_level": access_level,
            "selected_columns": [],
            "candidate_count": 0,
            "status": "no_rag_candidates",
            "candidates": [],
            "guardrails": {
                "embedded_structure_indexed": False,
                "analytics_values_reclassified_as_rag": False,
                "direct_vector_db_write_performed": False,
            },
        }

    try:
        dialect = csv.Sniffer().sniff(
            text[
                :10000
            ],
            delimiters=",;\t|",
        )

    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(
        text.splitlines(),
        dialect=dialect,
    )

    original_fields = (
        reader.fieldnames
        or []
    )

    fields = [
        (
            field.strip()
            if field
            else ""
        )
        for field in original_fields
    ]

    candidates: list[
        dict[str, Any]
    ] = []

    source_hash = hashlib.sha256(
        raw
    ).hexdigest()

    for row_number, row in enumerate(
        reader,
        start=1,
    ):
        if row_number > sample_rows:
            break

        normalized = {
            clean_name: str(
                row.get(
                    original
                )
                or ""
            ).strip()
            for original, clean_name in zip(
                original_fields,
                fields,
            )
        }

        for column in selected_columns:
            body = normalized.get(
                column,
                "",
            ).strip()

            if not body:
                continue

            candidate_key = hashlib.sha256(
                (
                    f"{dataset_name}|"
                    f"{source_hash}|"
                    f"{row_number}|"
                    f"{column}|"
                    f"{body}"
                ).encode(
                    "utf-8"
                )
            ).hexdigest()

            candidates.append(
                {
                    "candidate_key": candidate_key,
                    "dataset_name": dataset_name,
                    "source_filename": path.name,
                    "source_sha256": source_hash,
                    "source_row_number": row_number,
                    "source_column": column,
                    "title": (
                        f"Bundle normalized context | "
                        f"{dataset_name} | "
                        f"row {row_number} | "
                        f"{column}"
                    ),
                    "body": body,
                    "document_type": (
                        "normalized_csv_context"
                    ),
                    "access_level": access_level,
                }
            )

    return {
        "source": "unstructured_rag_routing",
        "routing_version": "22.7",
        "dataset_name": dataset_name,
        "filename": path.name,
        "source_sha256": source_hash,
        "access_level": access_level,
        "selected_columns": selected_columns,
        "candidate_count": len(
            candidates
        ),
        "status": (
            "rag_candidates_ready"
            if candidates
            else "no_rag_candidates"
        ),
        "candidates": candidates,
        "guardrails": {
            "embedded_structure_indexed": (
                include_embedded_structure
            ),
            "analytics_values_reclassified_as_rag": False,
            "direct_vector_db_write_performed": False,
            "role_filtered_retrieval_expected": True,
        },
        "next_stage": (
            "22.8_source_lineage_traceability"
        ),
    }


def persist_rag_route(
    result: dict[str, Any],
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO bundle.normalization_rag_routes (
                    dataset_name,
                    source_filename,
                    source_sha256,
                    routing_version,
                    access_level,
                    selected_columns,
                    candidate_count,
                    status,
                    result_json,
                    created_by,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s::jsonb,
                    %s, NOW()
                )
                RETURNING
                    id AS rag_route_id,
                    created_at
                """,
                (
                    result[
                        "dataset_name"
                    ],
                    result[
                        "filename"
                    ],
                    result[
                        "source_sha256"
                    ],
                    result[
                        "routing_version"
                    ],
                    result[
                        "access_level"
                    ],
                    json.dumps(
                        result[
                            "selected_columns"
                        ]
                    ),
                    result[
                        "candidate_count"
                    ],
                    result[
                        "status"
                    ],
                    json.dumps(
                        result
                    ),
                    created_by,
                ),
            )

            route_row = cursor.fetchone()

            route_id = route_row[
                "rag_route_id"
            ]

            for candidate in result.get(
                "candidates",
                [],
            ):
                cursor.execute(
                    """
                    INSERT INTO bundle.normalization_rag_queue (
                        rag_route_id,
                        candidate_key,
                        dataset_name,
                        source_filename,
                        source_sha256,
                        source_row_number,
                        source_column,
                        title,
                        body,
                        document_type,
                        access_level,
                        queue_status,
                        created_by,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, 'pending_export', %s, NOW()
                    )
                    ON CONFLICT (candidate_key)
                    DO NOTHING
                    """,
                    (
                        route_id,
                        candidate[
                            "candidate_key"
                        ],
                        candidate[
                            "dataset_name"
                        ],
                        candidate[
                            "source_filename"
                        ],
                        candidate[
                            "source_sha256"
                        ],
                        candidate[
                            "source_row_number"
                        ],
                        candidate[
                            "source_column"
                        ],
                        candidate[
                            "title"
                        ],
                        candidate[
                            "body"
                        ],
                        candidate[
                            "document_type"
                        ],
                        candidate[
                            "access_level"
                        ],
                        created_by,
                    ),
                )

        connection.commit()

    return {
        **result,
        "rag_route_id": route_id,
        "persisted_at": route_row[
            "created_at"
        ],
    }


def list_rag_queue(
    *,
    limit: int = 100,
    status: str | None = None,
) -> dict[str, Any]:
    allowed = {
        "pending_export",
        "exported",
        "ingested",
        "failed",
    }

    if (
        status is not None
        and status not in allowed
    ):
        raise ValueError(
            "status must be pending_export, exported, ingested, or failed."
        )

    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            1000,
        ),
    )

    query = """
        SELECT
            id AS queue_id,
            rag_route_id,
            candidate_key,
            dataset_name,
            source_filename,
            source_sha256,
            source_row_number,
            source_column,
            title,
            body,
            document_type,
            access_level,
            queue_status,
            export_batch_id,
            created_by,
            created_at,
            updated_at
        FROM bundle.normalization_rag_queue
    """

    params: list[
        Any
    ] = []

    if status is not None:
        query += (
            " WHERE queue_status = %s"
        )

        params.append(
            status
        )

    query += """
        ORDER BY id DESC
        LIMIT %s
    """

    params.append(
        safe_limit
    )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

    return {
        "source": "normalization_rag_queue",
        "items": rows,
    }


def export_pending_rag_queue(
    *,
    output_path: str | Path,
    limit: int = 1000,
) -> dict[str, Any]:
    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            10000,
        ),
    )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS queue_id,
                    candidate_key,
                    dataset_name,
                    source_filename,
                    source_sha256,
                    source_row_number,
                    source_column,
                    title,
                    body,
                    document_type,
                    access_level
                FROM bundle.normalization_rag_queue
                WHERE queue_status = 'pending_export'
                ORDER BY id
                LIMIT %s
                FOR UPDATE
                """,
                (
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

            if not rows:
                return {
                    "source": "normalization_rag_export",
                    "status": "nothing_to_export",
                    "exported_count": 0,
                    "output_path": str(
                        output
                    ),
                }

            batch_id = hashlib.sha256(
                "|".join(
                    str(
                        row[
                            "candidate_key"
                        ]
                    )
                    for row in rows
                ).encode(
                    "utf-8"
                )
            ).hexdigest()[
                :16
            ]

            with output.open(
                "w",
                encoding="utf-8",
            ) as handle:
                for row in rows:
                    payload = {
                        **dict(
                            row
                        ),
                        "export_batch_id": batch_id,
                    }

                    handle.write(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )

            ids = [
                row[
                    "queue_id"
                ]
                for row in rows
            ]

            cursor.execute(
                """
                UPDATE bundle.normalization_rag_queue
                SET
                    queue_status = 'exported',
                    export_batch_id = %s,
                    updated_at = NOW()
                WHERE id = ANY(%s)
                """,
                (
                    batch_id,
                    ids,
                ),
            )

        connection.commit()

    return {
        "source": "normalization_rag_export",
        "status": "exported",
        "export_batch_id": batch_id,
        "exported_count": len(
            rows
        ),
        "output_path": str(
            output
        ),
    }

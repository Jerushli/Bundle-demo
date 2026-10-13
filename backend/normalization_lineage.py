from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from backend.database import get_database_connection


ALLOWED_TARGET_SYSTEMS = {
    "analytics",
    "rag",
}


def _safe_limit(limit: int) -> int:
    return max(
        1,
        min(
            int(limit),
            500,
        ),
    )


def reconcile_rag_mapping(
    mapping_path: str | Path,
    *,
    reconciled_by: str | None = None,
) -> dict[str, Any]:
    path = Path(mapping_path)

    if not path.exists():
        raise ValueError(
            f"RAG mapping file does not exist: {path}"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    documents = payload.get(
        "documents",
        [],
    )

    if not isinstance(
        documents,
        list,
    ):
        raise ValueError(
            "RAG mapping file has invalid documents structure."
        )

    updated = 0
    missing = 0

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            for item in documents:
                candidate_key = str(
                    item.get(
                        "candidate_key",
                        "",
                    )
                ).strip()

                document_id_raw = item.get(
                    "document_id"
                )

                access_level = item.get(
                    "access_level"
                )

                if not candidate_key:
                    raise ValueError(
                        "RAG mapping item is missing candidate_key."
                    )

                if document_id_raw is None:
                    raise ValueError(
                        f"RAG mapping item {candidate_key} "
                        "is missing document_id."
                    )

                # IMPORTANT:
                # RAG document IDs are identifiers, not numeric quantities.
                # Existing Bundle RAG IDs can be values such as:
                #   DOC-00000377
                #   NORM-DB3A8BCF...
                # Preserve the exact identifier as text.
                document_id = str(
                    document_id_raw
                ).strip()

                if not document_id:
                    raise ValueError(
                        f"RAG mapping item {candidate_key} "
                        "contains an empty document_id."
                    )

                cursor.execute(
                    """
                    UPDATE bundle.normalization_rag_queue
                    SET
                        queue_status = 'ingested',
                        rag_document_id = %s,
                        rag_access_level_confirmed = %s,
                        reconciled_by = %s,
                        reconciled_at = NOW(),
                        updated_at = NOW()
                    WHERE candidate_key = %s
                    RETURNING
                        id AS queue_id,
                        dataset_name,
                        source_filename,
                        source_sha256,
                        source_row_number,
                        source_column
                    """,
                    (
                        document_id,
                        access_level,
                        reconciled_by,
                        candidate_key,
                    ),
                )

                row = cursor.fetchone()

                if row is None:
                    missing += 1
                    continue

                updated += 1

                cursor.execute(
                    """
                    INSERT INTO bundle.normalization_lineage (
                        dataset_name,
                        source_filename,
                        source_sha256,
                        source_row_number,
                        source_column,
                        target_system,
                        target_locator,
                        target_record_key,
                        lineage_status,
                        metadata_json,
                        created_by,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        'rag', %s, %s,
                        'confirmed',
                        %s::jsonb,
                        %s,
                        NOW()
                    )
                    ON CONFLICT (
                        dataset_name,
                        source_sha256,
                        source_row_number,
                        source_column,
                        target_system,
                        target_record_key
                    )
                    DO UPDATE SET
                        target_locator = EXCLUDED.target_locator,
                        lineage_status = 'confirmed',
                        metadata_json = EXCLUDED.metadata_json,
                        created_by = EXCLUDED.created_by
                    """,
                    (
                        row[
                            "dataset_name"
                        ],
                        row[
                            "source_filename"
                        ],
                        row[
                            "source_sha256"
                        ],
                        row[
                            "source_row_number"
                        ],
                        row[
                            "source_column"
                        ],
                        "rag.documents",
                        document_id,
                        json.dumps(
                            {
                                "candidate_key": candidate_key,
                                "rag_document_id": document_id,
                                "access_level": access_level,
                                "mapping_file": path.name,
                                "model_name": payload.get(
                                    "model_name"
                                ),
                            }
                        ),
                        reconciled_by,
                    ),
                )

        connection.commit()

    return {
        "source": "normalization_lineage",
        "operation": "reconcile_rag_mapping",
        "mapping_file": str(path),
        "mapping_document_count": len(
            documents
        ),
        "updated_queue_rows": updated,
        "missing_queue_rows": missing,
        "status": (
            "reconciled"
            if updated > 0
            else "nothing_reconciled"
        ),
    }


def register_analytics_lineage(
    *,
    route_id: int,
    created_by: str | None = None,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS route_id,
                    dataset_name,
                    source_filename,
                    source_sha256,
                    analytics_schema,
                    analytics_table,
                    routed_count,
                    blocked_count,
                    status
                FROM bundle.normalization_structured_routes
                WHERE id = %s
                """,
                (route_id,),
            )

            route = cursor.fetchone()

            if route is None:
                raise ValueError(
                    "Structured route not found."
                )

            table_ref = sql.Identifier(
                route[
                    "analytics_schema"
                ],
                route[
                    "analytics_table"
                ],
            )

            cursor.execute(
                sql.SQL(
                    """
                    SELECT
                        _bundle_source_row,
                        _bundle_source_column,
                        _bundle_route_reason,
                        _bundle_source_file,
                        _bundle_source_sha256
                    FROM {}
                    ORDER BY
                        _bundle_source_row,
                        _bundle_source_column
                    """
                ).format(
                    table_ref
                )
            )

            rows = cursor.fetchall()

            inserted = 0

            for row in rows:
                source_row = row[
                    "_bundle_source_row"
                ]

                source_column = row[
                    "_bundle_source_column"
                ]

                record_key = (
                    f"{source_row}:"
                    f"{source_column}"
                )

                cursor.execute(
                    """
                    INSERT INTO bundle.normalization_lineage (
                        dataset_name,
                        source_filename,
                        source_sha256,
                        source_row_number,
                        source_column,
                        target_system,
                        target_locator,
                        target_record_key,
                        lineage_status,
                        metadata_json,
                        created_by,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        'analytics', %s, %s,
                        'confirmed',
                        %s::jsonb,
                        %s,
                        NOW()
                    )
                    ON CONFLICT (
                        dataset_name,
                        source_sha256,
                        source_row_number,
                        source_column,
                        target_system,
                        target_record_key
                    )
                    DO UPDATE SET
                        target_locator = EXCLUDED.target_locator,
                        lineage_status = 'confirmed',
                        metadata_json = EXCLUDED.metadata_json,
                        created_by = EXCLUDED.created_by
                    """,
                    (
                        route[
                            "dataset_name"
                        ],
                        row[
                            "_bundle_source_file"
                        ]
                        or route[
                            "source_filename"
                        ],
                        row[
                            "_bundle_source_sha256"
                        ]
                        or route[
                            "source_sha256"
                        ],
                        source_row,
                        source_column,
                        (
                            f"{route['analytics_schema']}."
                            f"{route['analytics_table']}"
                        ),
                        record_key,
                        json.dumps(
                            {
                                "route_id": route_id,
                                "route_reason": row[
                                    "_bundle_route_reason"
                                ],
                                "route_status": route[
                                    "status"
                                ],
                            }
                        ),
                        created_by,
                    ),
                )

                inserted += 1

        connection.commit()

    return {
        "source": "normalization_lineage",
        "operation": "register_analytics_lineage",
        "route_id": route_id,
        "analytics_table": (
            f"{route['analytics_schema']}."
            f"{route['analytics_table']}"
        ),
        "registered_records": inserted,
        "status": "registered",
    }


def trace_source(
    *,
    dataset_name: str,
    source_row_number: int | None = None,
    source_column: str | None = None,
    source_sha256: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    safe_limit = _safe_limit(
        limit
    )

    conditions = [
        "dataset_name = %s"
    ]

    params: list[Any] = [
        dataset_name
    ]

    if source_row_number is not None:
        conditions.append(
            "source_row_number = %s"
        )
        params.append(
            source_row_number
        )

    if source_column is not None:
        conditions.append(
            "source_column = %s"
        )
        params.append(
            source_column
        )

    if source_sha256 is not None:
        conditions.append(
            "source_sha256 = %s"
        )
        params.append(
            source_sha256
        )

    params.append(
        safe_limit
    )

    query = f"""
        SELECT
            id AS lineage_id,
            dataset_name,
            source_filename,
            source_sha256,
            source_row_number,
            source_column,
            target_system,
            target_locator,
            target_record_key,
            lineage_status,
            metadata_json,
            created_by,
            created_at
        FROM bundle.normalization_lineage
        WHERE {" AND ".join(conditions)}
        ORDER BY
            source_row_number,
            source_column,
            target_system,
            id
        LIMIT %s
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                params,
            )
            rows = cursor.fetchall()

    target_counts = {
        "analytics": 0,
        "rag": 0,
    }

    for row in rows:
        target = row[
            "target_system"
        ]

        if target in target_counts:
            target_counts[
                target
            ] += 1

    return {
        "source": "normalization_lineage",
        "dataset_name": dataset_name,
        "filters": {
            "source_row_number": source_row_number,
            "source_column": source_column,
            "source_sha256": source_sha256,
        },
        "trace_count": len(
            rows
        ),
        "target_counts": target_counts,
        "traces": rows,
    }


def trace_target(
    *,
    target_system: str,
    target_record_key: str | None = None,
    target_locator: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if target_system not in ALLOWED_TARGET_SYSTEMS:
        raise ValueError(
            "target_system must be analytics or rag."
        )

    safe_limit = _safe_limit(
        limit
    )

    conditions = [
        "target_system = %s"
    ]

    params: list[Any] = [
        target_system
    ]

    if target_record_key is not None:
        conditions.append(
            "target_record_key = %s"
        )
        params.append(
            target_record_key
        )

    if target_locator is not None:
        conditions.append(
            "target_locator = %s"
        )
        params.append(
            target_locator
        )

    params.append(
        safe_limit
    )

    query = f"""
        SELECT
            id AS lineage_id,
            dataset_name,
            source_filename,
            source_sha256,
            source_row_number,
            source_column,
            target_system,
            target_locator,
            target_record_key,
            lineage_status,
            metadata_json,
            created_by,
            created_at
        FROM bundle.normalization_lineage
        WHERE {" AND ".join(conditions)}
        ORDER BY id DESC
        LIMIT %s
    """

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
        "source": "normalization_lineage",
        "target_system": target_system,
        "target_record_key": target_record_key,
        "target_locator": target_locator,
        "trace_count": len(
            rows
        ),
        "traces": rows,
    }


def lineage_summary(
    *,
    dataset_name: str,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    target_system,
                    lineage_status,
                    count(*) AS record_count
                FROM bundle.normalization_lineage
                WHERE dataset_name = %s
                GROUP BY
                    target_system,
                    lineage_status
                ORDER BY
                    target_system,
                    lineage_status
                """,
                (
                    dataset_name,
                ),
            )

            rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    count(*) FILTER (
                        WHERE queue_status = 'ingested'
                    ) AS ingested_rag,
                    count(*) FILTER (
                        WHERE queue_status = 'exported'
                    ) AS exported_rag,
                    count(*) FILTER (
                        WHERE queue_status = 'pending_export'
                    ) AS pending_rag,
                    count(*) FILTER (
                        WHERE queue_status = 'failed'
                    ) AS failed_rag
                FROM bundle.normalization_rag_queue
                WHERE dataset_name = %s
                """,
                (
                    dataset_name,
                ),
            )

            rag_state = cursor.fetchone()

    return {
        "source": "normalization_lineage",
        "dataset_name": dataset_name,
        "lineage_counts": rows,
        "rag_queue_state": dict(
            rag_state
        ),
    }

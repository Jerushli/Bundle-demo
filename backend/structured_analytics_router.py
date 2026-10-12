from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.normalization_review import run_confidence_review


SAFE_DATASET = re.compile(r"[^a-z0-9_]+")


def normalize_dataset_name(
    value: str,
) -> str:
    cleaned = value.strip().lower()

    cleaned = SAFE_DATASET.sub(
        "_",
        cleaned,
    )

    cleaned = re.sub(
        r"_+",
        "_",
        cleaned,
    ).strip("_")

    if not cleaned:
        raise ValueError(
            "dataset_name must contain letters or numbers."
        )

    if cleaned[0].isdigit():
        cleaned = (
            "dataset_"
            + cleaned
        )

    return cleaned[:50]


def _is_iso_date(
    value: Any,
) -> bool:
    if not isinstance(
        value,
        str,
    ):
        return False

    try:
        date.fromisoformat(
            value
        )
        return True

    except ValueError:
        return False


def _infer_sql_type(
    values: list[Any],
) -> str:
    non_null = [
        value
        for value in values
        if value is not None
        and value != ""
    ]

    if not non_null:
        return "TEXT"

    if all(
        isinstance(
            value,
            bool,
        )
        for value in non_null
    ):
        return "BOOLEAN"

    if all(
        isinstance(
            value,
            int,
        )
        and not isinstance(
            value,
            bool,
        )
        for value in non_null
    ):
        return "BIGINT"

    if all(
        isinstance(
            value,
            (
                int,
                float,
                Decimal,
            ),
        )
        and not isinstance(
            value,
            bool,
        )
        for value in non_null
    ):
        return "NUMERIC"

    if all(
        _is_iso_date(
            value
        )
        for value in non_null
    ):
        return "DATE"

    return "TEXT"


def _review_decisions(
    *,
    dataset_name: str,
) -> dict[
    tuple[
        int | None,
        str | None,
    ],
    str,
]:
    query = """
        SELECT DISTINCT ON (
            source_row_number,
            source_column
        )
            source_row_number,
            source_column,
            review_status
        FROM bundle.normalization_review_queue
        WHERE dataset_name = %s
        ORDER BY
            source_row_number,
            source_column,
            reviewed_at DESC NULLS LAST,
            id DESC
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    dataset_name,
                ),
            )

            rows = cursor.fetchall()

    return {
        (
            row[
                "source_row_number"
            ],
            row[
                "source_column"
            ],
        ): row[
            "review_status"
        ]
        for row in rows
    }


def prepare_structured_rows(
    review_result: dict[str, Any],
    *,
    review_decisions: dict[
        tuple[
            int | None,
            str | None,
        ],
        str,
    ] | None = None,
) -> dict[str, Any]:
    decisions = (
        review_decisions
        or {}
    )

    routed_rows: list[
        dict[str, Any]
    ] = []

    blocked_rows: list[
        dict[str, Any]
    ] = []

    for record in review_result.get(
        "records",
        [],
    ):
        routing_status = record.get(
            "routing_status"
        )

        decision = decisions.get(
            (
                record.get(
                    "source_row_number"
                ),
                record.get(
                    "source_column"
                ),
            )
        )

        allowed = False
        route_reason = None

        if (
            routing_status
            == "eligible_for_routing"
        ):
            allowed = True
            route_reason = (
                "high_confidence_validated"
            )

        elif (
            routing_status
            == "needs_human_review"
            and decision
            == "approved"
        ):
            allowed = True
            route_reason = (
                "human_review_approved"
            )

        elif (
            routing_status
            == "needs_human_review"
        ):
            route_reason = (
                "human_review_not_approved"
            )

        elif (
            routing_status
            == "blocked"
        ):
            route_reason = (
                "validation_blocked"
            )

        fields = record.get(
            "normalized_fields",
            {},
        )

        if allowed and fields:
            routed_rows.append(
                {
                    "_bundle_source_row": record.get(
                        "source_row_number"
                    ),
                    "_bundle_source_column": record.get(
                        "source_column"
                    ),
                    "_bundle_route_reason": route_reason,
                    **fields,
                }
            )

        else:
            blocked_rows.append(
                {
                    "source_row_number": record.get(
                        "source_row_number"
                    ),
                    "source_column": record.get(
                        "source_column"
                    ),
                    "routing_status": routing_status,
                    "review_decision": decision,
                    "reason": route_reason,
                }
            )

    dynamic_fields = sorted(
        {
            key
            for row in routed_rows
            for key in row.keys()
            if not key.startswith(
                "_bundle_"
            )
        }
    )

    column_types: dict[
        str,
        str,
    ] = {}

    for field in dynamic_fields:
        column_types[
            field
        ] = _infer_sql_type(
            [
                row.get(
                    field
                )
                for row in routed_rows
            ]
        )

    return {
        "routed_rows": routed_rows,
        "blocked_rows": blocked_rows,
        "dynamic_fields": dynamic_fields,
        "column_types": column_types,
        "routed_count": len(
            routed_rows
        ),
        "blocked_count": len(
            blocked_rows
        ),
    }


def _convert_for_sql(
    value: Any,
    sql_type: str,
) -> Any:
    if value is None:
        return None

    if (
        sql_type
        == "DATE"
        and isinstance(
            value,
            str,
        )
    ):
        return date.fromisoformat(
            value
        )

    return value


def route_structured_to_analytics(
    file_path: str | Path,
    *,
    dataset_name: str,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
    require_known_fields_only: bool = False,
    created_by: str | None = None,
) -> dict[str, Any]:
    safe_dataset = normalize_dataset_name(
        dataset_name
    )

    path = Path(
        file_path
    )

    raw = path.read_bytes()

    source_hash = hashlib.sha256(
        raw
    ).hexdigest()

    review_result = run_confidence_review(
        str(
            path
        ),
        columns=columns,
        sample_rows=sample_rows,
        require_known_fields_only=require_known_fields_only,
    )

    decisions = _review_decisions(
        dataset_name=dataset_name,
    )

    prepared = prepare_structured_rows(
        review_result,
        review_decisions=decisions,
    )

    if (
        prepared[
            "routed_count"
        ]
        == 0
    ):
        return {
            "source": "structured_analytics_routing",
            "routing_version": "22.6",
            "dataset_name": dataset_name,
            "status": "nothing_routable",
            "analytics_table": None,
            "source_sha256": source_hash,
            **prepared,
            "guardrails": {
                "active_dataset_changed": False,
                "existing_analytics_table_replaced": False,
                "pending_review_rows_loaded": False,
                "rejected_rows_loaded": False,
            },
        }

    table_name = (
        "norm_"
        + safe_dataset
        + "_"
        + source_hash[
            :8
        ]
    )

    dynamic_fields = prepared[
        "dynamic_fields"
    ]

    column_types = prepared[
        "column_types"
    ]

    fixed_columns = [
        (
            "_bundle_source_row",
            "BIGINT",
        ),
        (
            "_bundle_source_column",
            "TEXT",
        ),
        (
            "_bundle_route_reason",
            "TEXT",
        ),
        (
            "_bundle_source_file",
            "TEXT",
        ),
        (
            "_bundle_source_sha256",
            "TEXT",
        ),
        (
            "_bundle_loaded_at",
            "TIMESTAMPTZ",
        ),
    ]

    definitions = []

    for name, type_name in fixed_columns:
        definitions.append(
            sql.SQL("{} {}").format(
                sql.Identifier(
                    name
                ),
                sql.SQL(
                    type_name
                ),
            )
        )

    for field in dynamic_fields:
        definitions.append(
            sql.SQL("{} {}").format(
                sql.Identifier(
                    field
                ),
                sql.SQL(
                    column_types[
                        field
                    ]
                ),
            )
        )

    create_statement = sql.SQL(
        """
        CREATE TABLE {}.{} (
            {}
        )
        """
    ).format(
        sql.Identifier(
            "analytics"
        ),
        sql.Identifier(
            table_name
        ),
        sql.SQL(
            ", "
        ).join(
            definitions
        ),
    )

    insert_columns = [
        "_bundle_source_row",
        "_bundle_source_column",
        "_bundle_route_reason",
        "_bundle_source_file",
        "_bundle_source_sha256",
        "_bundle_loaded_at",
        *dynamic_fields,
    ]

    insert_statement = sql.SQL(
        "INSERT INTO {}.{} ({}) VALUES ({})"
    ).format(
        sql.Identifier(
            "analytics"
        ),
        sql.Identifier(
            table_name
        ),
        sql.SQL(
            ", "
        ).join(
            sql.Identifier(
                column
            )
            for column in insert_columns
        ),
        sql.SQL(
            ", "
        ).join(
            sql.Placeholder()
            for _ in insert_columns
        ),
    )

    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "CREATE SCHEMA IF NOT EXISTS {}"
                ).format(
                    sql.Identifier(
                        "analytics"
                    )
                )
            )

            # Versioned table name means we never overwrite an existing live
            # analytics table. Re-running the same source simply recreates the
            # same normalization artifact deterministically.
            cursor.execute(
                sql.SQL(
                    "DROP TABLE IF EXISTS {}.{}"
                ).format(
                    sql.Identifier(
                        "analytics"
                    ),
                    sql.Identifier(
                        table_name
                    ),
                )
            )

            cursor.execute(
                create_statement
            )

            for row in prepared[
                "routed_rows"
            ]:
                values = [
                    row.get(
                        "_bundle_source_row"
                    ),
                    row.get(
                        "_bundle_source_column"
                    ),
                    row.get(
                        "_bundle_route_reason"
                    ),
                    path.name,
                    source_hash,
                    datetime.now(),
                ]

                for field in dynamic_fields:
                    values.append(
                        _convert_for_sql(
                            row.get(
                                field
                            ),
                            column_types[
                                field
                            ],
                        )
                    )

                cursor.execute(
                    insert_statement,
                    values,
                )

            cursor.execute(
                """
                INSERT INTO bundle.normalization_structured_routes (
                    dataset_name,
                    source_filename,
                    source_sha256,
                    routing_version,
                    analytics_schema,
                    analytics_table,
                    routed_count,
                    blocked_count,
                    column_types,
                    status,
                    created_by,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::jsonb,
                    'ready_for_onboarding', %s, NOW()
                )
                RETURNING id
                """,
                (
                    dataset_name,
                    path.name,
                    source_hash,
                    "22.6",
                    "analytics",
                    table_name,
                    prepared[
                        "routed_count"
                    ],
                    prepared[
                        "blocked_count"
                    ],
                    json.dumps(
                        column_types
                    ),
                    created_by,
                ),
            )

            route_id = cursor.fetchone()[
                0
            ]

        connection.commit()

    return {
        "source": "structured_analytics_routing",
        "routing_version": "22.6",
        "route_id": route_id,
        "dataset_name": dataset_name,
        "status": "ready_for_onboarding",
        "analytics_schema": "analytics",
        "analytics_table": (
            "analytics."
            + table_name
        ),
        "source_filename": path.name,
        "source_sha256": source_hash,
        **prepared,
        "guardrails": {
            "active_dataset_changed": False,
            "existing_analytics_table_replaced": False,
            "pending_review_rows_loaded": False,
            "rejected_rows_loaded": False,
            "arbitrary_sql_used": False,
        },
        "next_stage": (
            "22.7_unstructured_secure_rag_routing"
        ),
    }


def list_structured_routes(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            200,
        ),
    )

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
                    routing_version,
                    analytics_schema,
                    analytics_table,
                    routed_count,
                    blocked_count,
                    column_types,
                    status,
                    created_by,
                    created_at
                FROM bundle.normalization_structured_routes
                ORDER BY id DESC
                LIMIT %s
                """,
                (
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "structured_analytics_routing",
        "routes": rows,
    }

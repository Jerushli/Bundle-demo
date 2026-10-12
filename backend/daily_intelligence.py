from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from backend.database import get_database_connection


ALLOWED_AGGREGATIONS = {
    "sum": "SUM",
    "avg": "AVG",
    "count": "COUNT",
    "min": "MIN",
    "max": "MAX",
}

NUMERIC_POSTGRES_TYPES = {
    "smallint",
    "integer",
    "bigint",
    "decimal",
    "numeric",
    "real",
    "double precision",
}

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ActiveDataset:
    dataset_name: str
    analytics_table: str
    schema_name: str
    table_name: str


def _parse_qualified_table_name(value: str) -> tuple[str, str]:
    """
    Accepts analytics.table_name or table_name.
    Unqualified names default to the analytics schema.
    """
    cleaned = (value or "").strip().strip('"')

    if not cleaned:
        raise ValueError("The active dataset does not have an analytics table.")

    parts = [
        part.strip().strip('"')
        for part in cleaned.split(".")
    ]

    if len(parts) == 1:
        schema_name = "analytics"
        table_name = parts[0]
    elif len(parts) == 2:
        schema_name, table_name = parts
    else:
        raise ValueError(
            "The active dataset analytics table has an invalid qualified name."
        )

    for identifier in (schema_name, table_name):
        if not IDENTIFIER_PATTERN.fullmatch(identifier):
            raise ValueError(
                "The active dataset analytics table contains an unsafe identifier."
            )

    return schema_name, table_name


def get_active_dataset() -> ActiveDataset:
    query = """
        SELECT
            dataset_name,
            analytics_table
        FROM bundle.dataset_registry
        WHERE is_active = TRUE
          AND status = 'ready'
        ORDER BY created_at DESC
        LIMIT 1
    """

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            "No active READY dataset is configured in bundle.dataset_registry."
        )

    schema_name, table_name = _parse_qualified_table_name(
        row["analytics_table"]
    )

    return ActiveDataset(
        dataset_name=row["dataset_name"],
        analytics_table=row["analytics_table"],
        schema_name=schema_name,
        table_name=table_name,
    )


def get_available_columns() -> dict[str, Any]:
    dataset = get_active_dataset()

    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
    """

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                query,
                (
                    dataset.schema_name,
                    dataset.table_name,
                ),
            )
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence",
        "dataset_name": dataset.dataset_name,
        "analytics_table": dataset.analytics_table,
        "columns": [
            {
                **row,
                "supported_for_numeric_kpi": (
                    row["data_type"] in NUMERIC_POSTGRES_TYPES
                ),
            }
            for row in rows
        ],
    }


def _column_metadata(
    connection,
    dataset: ActiveDataset,
    column_name: str,
) -> dict[str, Any] | None:
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
    """

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            query,
            (
                dataset.schema_name,
                dataset.table_name,
                column_name,
            ),
        )
        return cursor.fetchone()


def _validate_kpi_target(
    connection,
    dataset: ActiveDataset,
    *,
    column_name: str,
    aggregation: str,
) -> None:
    aggregation = aggregation.lower()

    if aggregation not in ALLOWED_AGGREGATIONS:
        raise ValueError(
            "Unsupported aggregation. Allowed values: "
            "sum, avg, count, min, max."
        )

    if aggregation == "count" and column_name == "*":
        return

    if not IDENTIFIER_PATTERN.fullmatch(column_name):
        raise ValueError("Unsafe KPI column name.")

    metadata = _column_metadata(
        connection,
        dataset,
        column_name,
    )

    if metadata is None:
        raise ValueError(
            f"Column '{column_name}' does not exist in the active analytics table."
        )

    if (
        aggregation in {"sum", "avg", "min", "max"}
        and metadata["data_type"] not in NUMERIC_POSTGRES_TYPES
    ):
        raise ValueError(
            f"Aggregation '{aggregation}' requires a numeric column. "
            f"Column '{column_name}' is {metadata['data_type']}."
        )


def create_kpi_definition(
    *,
    kpi_key: str,
    display_name: str,
    column_name: str,
    aggregation: str,
    enabled: bool = True,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    kpi_key = kpi_key.strip().lower()
    display_name = display_name.strip()
    column_name = column_name.strip()
    aggregation = aggregation.strip().lower()

    if not re.fullmatch(r"[a-z][a-z0-9_]{1,79}", kpi_key):
        raise ValueError(
            "kpi_key must start with a letter and contain only "
            "lowercase letters, numbers, and underscores."
        )

    if not display_name:
        raise ValueError("display_name cannot be empty.")

    with get_database_connection() as connection:
        _validate_kpi_target(
            connection,
            dataset,
            column_name=column_name,
            aggregation=aggregation,
        )

        query = """
            INSERT INTO bundle.intelligence_kpi_definitions (
                dataset_name,
                kpi_key,
                display_name,
                column_name,
                aggregation,
                enabled,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (dataset_name, kpi_key)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                column_name = EXCLUDED.column_name,
                aggregation = EXCLUDED.aggregation,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING
                id,
                dataset_name,
                kpi_key,
                display_name,
                column_name,
                aggregation,
                enabled,
                created_at,
                updated_at
        """

        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                query,
                (
                    dataset.dataset_name,
                    kpi_key,
                    display_name,
                    column_name,
                    aggregation,
                    enabled,
                ),
            )
            row = cursor.fetchone()

        connection.commit()

    return dict(row)


def list_kpi_definitions(
    *,
    include_disabled: bool = False,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    query = """
        SELECT
            id,
            dataset_name,
            kpi_key,
            display_name,
            column_name,
            aggregation,
            enabled,
            created_at,
            updated_at
        FROM bundle.intelligence_kpi_definitions
        WHERE dataset_name = %s
    """

    params: list[Any] = [dataset.dataset_name]

    if not include_disabled:
        query += " AND enabled = TRUE"

    query += " ORDER BY id"

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence",
        "dataset_name": dataset.dataset_name,
        "analytics_table": dataset.analytics_table,
        "kpis": rows,
    }


def _build_metric_expression(
    aggregation: str,
    column_name: str,
):
    function_name = ALLOWED_AGGREGATIONS[aggregation]

    if aggregation == "count" and column_name == "*":
        return sql.SQL("COUNT(*)")

    return sql.SQL("{}({})").format(
        sql.SQL(function_name),
        sql.Identifier(column_name),
    )


def generate_daily_snapshot(
    *,
    snapshot_date: date | None = None,
) -> dict[str, Any]:
    dataset = get_active_dataset()
    target_date = snapshot_date or date.today()

    definitions_query = """
        SELECT
            id,
            kpi_key,
            display_name,
            column_name,
            aggregation
        FROM bundle.intelligence_kpi_definitions
        WHERE dataset_name = %s
          AND enabled = TRUE
        ORDER BY id
    """

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                definitions_query,
                (dataset.dataset_name,),
            )
            definitions = cursor.fetchall()

        if not definitions:
            return {
                "source": "daily_intelligence",
                "dataset_name": dataset.dataset_name,
                "analytics_table": dataset.analytics_table,
                "snapshot_date": target_date.isoformat(),
                "status": "no_kpis_configured",
                "row_count": None,
                "kpis": [],
                "message": (
                    "No enabled KPI definitions exist for the active dataset."
                ),
            }

        valid_definitions: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        for definition in definitions:
            try:
                _validate_kpi_target(
                    connection,
                    dataset,
                    column_name=definition["column_name"],
                    aggregation=definition["aggregation"],
                )
                valid_definitions.append(definition)
            except ValueError as exc:
                failures.append(
                    {
                        "kpi_definition_id": definition["id"],
                        "kpi_key": definition["kpi_key"],
                        "display_name": definition["display_name"],
                        "status": "failed",
                        "value": None,
                        "error": str(exc),
                    }
                )

        values_by_id: dict[int, Any] = {}
        row_count: int | None = None

        if valid_definitions:
            select_items = [
                sql.SQL("COUNT(*) AS {}").format(
                    sql.Identifier("__bundle_row_count")
                )
            ]

            for definition in valid_definitions:
                alias = f"kpi_{definition['id']}"
                select_items.append(
                    sql.SQL("{} AS {}").format(
                        _build_metric_expression(
                            definition["aggregation"],
                            definition["column_name"],
                        ),
                        sql.Identifier(alias),
                    )
                )

            aggregate_query = sql.SQL(
                "SELECT {} FROM {}.{}"
            ).format(
                sql.SQL(", ").join(select_items),
                sql.Identifier(dataset.schema_name),
                sql.Identifier(dataset.table_name),
            )

            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(aggregate_query)
                aggregate_row = cursor.fetchone()

            row_count = int(
                aggregate_row["__bundle_row_count"]
            )

            for definition in valid_definitions:
                alias = f"kpi_{definition['id']}"
                values_by_id[definition["id"]] = aggregate_row[alias]

        results: list[dict[str, Any]] = []

        upsert_query = """
            INSERT INTO bundle.intelligence_kpi_snapshots (
                dataset_name,
                kpi_definition_id,
                snapshot_date,
                metric_value,
                row_count,
                status,
                error_message,
                generated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (kpi_definition_id, snapshot_date)
            DO UPDATE SET
                dataset_name = EXCLUDED.dataset_name,
                metric_value = EXCLUDED.metric_value,
                row_count = EXCLUDED.row_count,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                generated_at = NOW()
            RETURNING id, generated_at
        """

        with connection.cursor(row_factory=dict_row) as cursor:
            for definition in valid_definitions:
                raw_value = values_by_id.get(definition["id"])

                metric_value = (
                    Decimal(str(raw_value))
                    if raw_value is not None
                    else None
                )

                cursor.execute(
                    upsert_query,
                    (
                        dataset.dataset_name,
                        definition["id"],
                        target_date,
                        metric_value,
                        row_count,
                        "success",
                        None,
                    ),
                )
                stored = cursor.fetchone()

                results.append(
                    {
                        "snapshot_id": stored["id"],
                        "kpi_definition_id": definition["id"],
                        "kpi_key": definition["kpi_key"],
                        "display_name": definition["display_name"],
                        "aggregation": definition["aggregation"],
                        "column_name": definition["column_name"],
                        "status": "success",
                        "value": metric_value,
                        "generated_at": stored["generated_at"],
                    }
                )

            for failure in failures:
                cursor.execute(
                    upsert_query,
                    (
                        dataset.dataset_name,
                        failure["kpi_definition_id"],
                        target_date,
                        None,
                        row_count,
                        "failed",
                        failure["error"][:1000],
                    ),
                )
                stored = cursor.fetchone()

                results.append(
                    {
                        "snapshot_id": stored["id"],
                        **failure,
                        "generated_at": stored["generated_at"],
                    }
                )

        connection.commit()

    if failures and valid_definitions:
        overall_status = "completed_with_warnings"
    elif failures and not valid_definitions:
        overall_status = "failed"
    else:
        overall_status = "completed"

    results.sort(
        key=lambda item: item["kpi_definition_id"]
    )

    return {
        "source": "daily_intelligence",
        "dataset_name": dataset.dataset_name,
        "analytics_table": dataset.analytics_table,
        "snapshot_date": target_date.isoformat(),
        "status": overall_status,
        "row_count": row_count,
        "kpis": results,
    }


def get_snapshots(
    *,
    limit: int = 100,
) -> dict[str, Any]:
    dataset = get_active_dataset()
    safe_limit = max(1, min(int(limit), 500))

    query = """
        SELECT
            s.id AS snapshot_id,
            s.snapshot_date,
            s.metric_value,
            s.row_count,
            s.status,
            s.error_message,
            s.generated_at,
            d.id AS kpi_definition_id,
            d.kpi_key,
            d.display_name,
            d.column_name,
            d.aggregation
        FROM bundle.intelligence_kpi_snapshots s
        JOIN bundle.intelligence_kpi_definitions d
          ON d.id = s.kpi_definition_id
        WHERE s.dataset_name = %s
        ORDER BY
            s.snapshot_date DESC,
            d.id ASC
        LIMIT %s
    """

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                query,
                (
                    dataset.dataset_name,
                    safe_limit,
                ),
            )
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence",
        "dataset_name": dataset.dataset_name,
        "analytics_table": dataset.analytics_table,
        "snapshots": rows,
    }

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import sql

from backend.dataset_profiles import (
    get_active_dataset_name,
    get_latest_business_profile,
)

from backend.dataset_security import (
    DatasetPermission,
    clamp_result_limit,
    enforce_column_access,
    enforce_dataset_access,
    enforce_operation_access,
    filter_allowed_columns,
    get_dataset_permission,
)
from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


ALLOWED_AGGREGATIONS = {
    "sum",
    "average",
    "minimum",
    "maximum",
    "count",
}

ALLOWED_OPERATIONS = {
    "aggregate",
    "group",
    "compare",
    "trend",
}

ALLOWED_DATE_GRAINS = {
    "month",
    "year",
}


@dataclass(frozen=True)
class DatasetSchema:
    dataset_name: str
    analytics_table: str
    measures: list[str]
    categories: list[str]
    dates: list[str]
    identifiers: list[str]
    text_columns: list[str]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def _latest_validation_report(
    connection,
    dataset_name: str,
) -> dict[str, Any]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT report_json
            FROM staging.validation_reports
            WHERE dataset_name = %s
            ORDER BY
                CASE
                    WHEN validation_mode = 'full'
                    THEN 0
                    ELSE 1
                END,
                created_at DESC
            LIMIT 1
            """,
            (dataset_name,),
        )

        row = cur.fetchone()

    if not row:
        raise ValueError(
            f"No validated schema exists for dataset {dataset_name!r}."
        )

    payload = row[0]

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    return dict(payload)


def get_active_dataset_schema(
    role: str = "analyst",
) -> DatasetSchema:
    dataset_name = get_active_dataset_name()

    permission = get_dataset_permission(
        dataset_name=dataset_name,
        role=role,
    )

    enforce_dataset_access(
        permission=permission
    )
    profile = get_latest_business_profile(
        dataset_name
    )

    analytics_table = str(
        profile.get(
            "analytics_table",
            f"analytics.{sanitize_identifier(dataset_name)}_clean",
        )
    )

    if "." in analytics_table:
        _, table_name = analytics_table.split(
            ".",
            1,
        )
    else:
        table_name = analytics_table

    measures: list[str] = []
    categories: list[str] = []
    dates: list[str] = []
    identifiers: list[str] = []
    text_columns: list[str] = []

    with get_ingest_connection() as connection:
        report = _latest_validation_report(
            connection,
            dataset_name,
        )

        # Stage 7.2 hardening:
        # treat the actual typed analytics table as the final authority
        # for date/timestamp columns. This protects trend routing if an
        # earlier profile missed the date role even though Stage 4
        # successfully created a DATE/TIMESTAMP column.
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE
                    table_schema = 'analytics'
                    AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )

            typed_columns = {
                str(row[0]): str(row[1]).lower()
                for row in cur.fetchall()
            }

    for column in report.get("columns", []):
        name = str(
            column.get(
                "column_name",
                "",
            )
        )

        if not name:
            continue

        column_role = str(
            column.get(
                "proposed_role",
                "",
            )
        )

        proposed_type = str(
            column.get(
                "proposed_type",
                "",
            )
        )

        rag_candidate = bool(
            column.get(
                "rag_candidate",
                False,
            )
        )

        if (
            column_role == "measure"
            and proposed_type in {
                "integer",
                "numeric",
            }
        ):
            measures.append(name)
            continue

        if (
            column_role == "date_dimension"
            or proposed_type == "date"
        ):
            dates.append(name)
            continue

        if column_role in {
            "category",
            "dimension",
        }:
            categories.append(name)
            continue

        if column_role == "identifier":
            identifiers.append(name)
            continue

        if (
            proposed_type == "text"
            or rag_candidate
        ):
            text_columns.append(name)

    # Add any actual PostgreSQL DATE/TIMESTAMP columns that were not
    # identified as dates in the earlier profile metadata.
    for column_name, data_type in typed_columns.items():
        if data_type in {
            "date",
            "timestamp without time zone",
            "timestamp with time zone",
        } and column_name not in dates:
            dates.append(column_name)

            # A column cannot simultaneously be treated as a normal
            # categorical dimension in the structured router.
            if column_name in categories:
                categories.remove(column_name)

            if column_name in text_columns:
                text_columns.remove(column_name)

    measures = filter_allowed_columns(
        permission=permission,
        columns=measures,
    )

    categories = filter_allowed_columns(
        permission=permission,
        columns=categories,
    )

    dates = filter_allowed_columns(
        permission=permission,
        columns=dates,
    )

    identifiers = filter_allowed_columns(
        permission=permission,
        columns=identifiers,
    )

    text_columns = filter_allowed_columns(
        permission=permission,
        columns=text_columns,
    )

    return DatasetSchema(
        dataset_name=dataset_name,
        analytics_table=table_name,
        measures=measures,
        categories=categories,
        dates=dates,
        identifiers=identifiers,
        text_columns=text_columns,
    )


def _assert_allowed(
    value: str | None,
    allowed: list[str],
    label: str,
    *,
    allow_none: bool = False,
):
    if value is None and allow_none:
        return

    if value not in allowed:
        raise ValueError(
            f"{label} {value!r} is not allowed for the active dataset."
        )


def _aggregation_expression(
    aggregation: str,
    measure: str | None,
):
    if aggregation not in ALLOWED_AGGREGATIONS:
        raise ValueError(
            f"Unsupported aggregation: {aggregation}"
        )

    if aggregation == "count":
        return sql.SQL("count(*)")

    if not measure:
        raise ValueError(
            f"Aggregation {aggregation!r} requires a measure."
        )

    identifier = sql.Identifier(
        measure
    )

    if aggregation == "sum":
        return sql.SQL(
            "SUM({})"
        ).format(
            identifier
        )

    if aggregation == "average":
        return sql.SQL(
            "AVG({})"
        ).format(
            identifier
        )

    if aggregation == "minimum":
        return sql.SQL(
            "MIN({})"
        ).format(
            identifier
        )

    if aggregation == "maximum":
        return sql.SQL(
            "MAX({})"
        ).format(
            identifier
        )

    raise ValueError(
        f"Unsupported aggregation: {aggregation}"
    )


def _build_filters(
    schema: DatasetSchema,
    filters: list[dict[str, Any]] | None,
    permission: DatasetPermission | None = None,
) -> tuple[Any, list[Any]]:
    if not filters:
        return sql.SQL("TRUE"), []

    allowed_filter_columns = (
        schema.categories
        + schema.dates
        + schema.identifiers
    )

    conditions = []
    params: list[Any] = []

    for item in filters[:8]:
        column = str(
            item.get(
                "column",
                "",
            )
        )

        value = item.get(
            "value"
        )

        if permission is not None:
            enforce_column_access(
                permission=permission,
                column=column,
            )

        _assert_allowed(
            column,
            allowed_filter_columns,
            "Filter column",
        )

        if value is None:
            raise ValueError(
                f"Filter {column!r} requires a value."
            )

        conditions.append(
            sql.SQL(
                "CAST({} AS TEXT) ILIKE %s"
            ).format(
                sql.Identifier(
                    column
                )
            )
        )

        params.append(
            str(value)
        )

    return (
        sql.SQL(" AND ").join(
            conditions
        ),
        params,
    )


def _table_ref(
    schema: DatasetSchema,
):
    return sql.SQL(
        "analytics.{}"
    ).format(
        sql.Identifier(
            schema.analytics_table
        )
    )


def execute_dataset_analysis(
    *,
    role: str = "analyst",
    operation: str,
    aggregation: str = "sum",
    measure: str | None = None,
    group_by: str | None = None,
    values: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 10,
    date_grain: str | None = None,
) -> dict[str, Any]:
    schema = get_active_dataset_schema(
        role=role
    )

    permission = get_dataset_permission(
        dataset_name=schema.dataset_name,
        role=role,
    )

    enforce_dataset_access(
        permission=permission
    )

    enforce_operation_access(
        permission=permission,
        operation=operation,
    )

    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(
            f"Unsupported operation: {operation}"
        )

    if measure is not None:
        enforce_column_access(
            permission=permission,
            column=measure,
        )

        _assert_allowed(
            measure,
            schema.measures,
            "Measure",
        )

    limit = clamp_result_limit(
        permission=permission,
        requested_limit=(
            int(limit or 10)
        ),
    )

    where_sql, params = _build_filters(
        schema,
        filters,
        permission=permission,
    )

    agg_expr = _aggregation_expression(
        aggregation,
        measure,
    )

    rows: list[dict[str, Any]] = []

    with get_ingest_connection() as connection:
        if operation == "aggregate":
            statement = sql.SQL(
                """
                SELECT {agg} AS value
                FROM {table}
                WHERE {where}
                """
            ).format(
                agg=agg_expr,
                table=_table_ref(
                    schema
                ),
                where=where_sql,
            )

            with connection.cursor() as cur:
                cur.execute(
                    statement,
                    params,
                )
                row = cur.fetchone()

            value = (
                _json_safe(
                    row[0]
                )
                if row
                else None
            )

            rows = [
                {
                    "group_name": "total",
                    "value": value,
                }
            ]

            result_group = "total"

        elif operation in {
            "group",
            "compare",
        }:
            enforce_column_access(
                permission=permission,
                column=group_by,
            )

            _assert_allowed(
                group_by,
                schema.categories,
                "Group column",
            )

            query_params = list(
                params
            )

            compare_condition = sql.SQL(
                "TRUE"
            )

            if operation == "compare":
                requested = [
                    str(value)
                    for value in (
                        values
                        or []
                    )
                    if str(
                        value
                    ).strip()
                ]

                if not requested:
                    raise ValueError(
                        "Compare requires at least one value."
                    )

                placeholders = sql.SQL(
                    ", "
                ).join(
                    sql.Placeholder()
                    for _ in requested
                )

                compare_condition = sql.SQL(
                    "CAST({} AS TEXT) IN ({})"
                ).format(
                    sql.Identifier(
                        group_by
                    ),
                    placeholders,
                )

                query_params.extend(
                    requested
                )

            statement = sql.SQL(
                """
                SELECT
                    CAST({group_by} AS TEXT) AS group_name,
                    {agg} AS value
                FROM {table}
                WHERE ({where})
                  AND ({compare_condition})
                  AND {group_by} IS NOT NULL
                GROUP BY {group_by}
                ORDER BY value DESC NULLS LAST, group_name
                LIMIT %s
                """
            ).format(
                group_by=sql.Identifier(
                    group_by
                ),
                agg=agg_expr,
                table=_table_ref(
                    schema
                ),
                where=where_sql,
                compare_condition=(
                    compare_condition
                ),
            )

            query_params.append(
                limit
            )

            with connection.cursor() as cur:
                cur.execute(
                    statement,
                    query_params,
                )

                for row in cur.fetchall():
                    rows.append(
                        {
                            "group_name": str(
                                row[0]
                            ),
                            "value": _json_safe(
                                row[1]
                            ),
                        }
                    )

            result_group = str(
                group_by
            )

        elif operation == "trend":
            # If the router/provider omits group_by, use the first
            # validated/typed date column automatically.
            if group_by is None:
                if schema.dates:
                    group_by = schema.dates[0]
                else:
                    raise ValueError(
                        "This active dataset has no validated DATE or "
                        "TIMESTAMP column for trend analysis."
                    )

            enforce_column_access(
                permission=permission,
                column=group_by,
            )

            _assert_allowed(
                group_by,
                schema.dates,
                "Date column",
            )

            # Monthly is the safe default for an unspecified trend grain.
            if date_grain is None:
                date_grain = "month"

            if date_grain not in ALLOWED_DATE_GRAINS:
                raise ValueError(
                    "Trend requires date_grain month or year."
                )

            if date_grain == "month":
                bucket = sql.SQL(
                    "date_trunc('month', {})"
                ).format(
                    sql.Identifier(
                        group_by
                    )
                )
            else:
                bucket = sql.SQL(
                    "date_trunc('year', {})"
                ).format(
                    sql.Identifier(
                        group_by
                    )
                )

            statement = sql.SQL(
                """
                SELECT
                    {bucket} AS bucket,
                    {agg} AS value
                FROM {table}
                WHERE ({where})
                  AND {date_column} IS NOT NULL
                GROUP BY bucket
                ORDER BY bucket ASC
                LIMIT %s
                """
            ).format(
                bucket=bucket,
                agg=agg_expr,
                table=_table_ref(
                    schema
                ),
                where=where_sql,
                date_column=sql.Identifier(
                    group_by
                ),
            )

            query_params = [
                *params,
                limit,
            ]

            with connection.cursor() as cur:
                cur.execute(
                    statement,
                    query_params,
                )

                for row in cur.fetchall():
                    rows.append(
                        {
                            "group_name": (
                                row[0].date().isoformat()
                                if isinstance(
                                    row[0],
                                    datetime,
                                )
                                else _json_safe(
                                    row[0]
                                )
                            ),
                            "value": _json_safe(
                                row[1]
                            ),
                        }
                    )

            result_group = (
                date_grain
            )

        else:
            raise ValueError(
                f"Unsupported operation: {operation}"
            )

    return {
        "dataset_name": schema.dataset_name,
        "operation": operation,
        "aggregation": aggregation,
        "metric": (
            measure
            or "count"
        ),
        "group_by": result_group,
        "rows": rows,
        "filters": filters or [],
        "date_grain": date_grain,
    }


def get_category_value_matches(
    question: str,
    *,
    role: str = "analyst",
    max_values_per_column: int = 250,
) -> dict[str, list[str]]:
    """
    Find category values that are literally mentioned in the question.

    This is used only for deterministic routing such as:
        "Compare sales for South India and North India."

    The LLM does not choose these values.
    """
    schema = get_active_dataset_schema(
        role=role
    )
    question_lower = question.lower()

    matches: dict[str, list[str]] = {}

    with get_ingest_connection() as connection:
        for column in schema.categories:
            statement = sql.SQL(
                """
                SELECT DISTINCT CAST({column} AS TEXT)
                FROM {table}
                WHERE {column} IS NOT NULL
                ORDER BY 1
                LIMIT %s
                """
            ).format(
                column=sql.Identifier(column),
                table=_table_ref(schema),
            )

            with connection.cursor() as cur:
                cur.execute(
                    statement,
                    (max_values_per_column,),
                )

                found: list[str] = []

                for row in cur.fetchall():
                    value = str(row[0]).strip()

                    if (
                        value
                        and value.lower()
                        in question_lower
                    ):
                        found.append(value)

                if found:
                    matches[column] = found

    return matches

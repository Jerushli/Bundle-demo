import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from psycopg import sql

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)

NULL_LIKE = ("", "null", "none", "n/a", "na", "nan", "-")
BOOLEAN_VALUES = ("true", "false", "yes", "no", "y", "n", "1", "0")

INTEGER_REGEX = r"^[+-]?\d+$"
NUMERIC_REGEX = r"^[₹$€£]?\s*[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?$"
DATE_REGEX = r"^(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|\d{4}/\d{2}/\d{2})$"


@dataclass
class ColumnValidation:
    column_name: str
    proposed_type: str
    proposed_role: str
    nullable: bool
    invalid_rows: int
    duplicate_rows: int | None
    conversion_safe: bool
    rag_candidate: bool
    warnings: list[str]


@dataclass
class ValidationReport:
    dataset_name: str
    staging_table: str
    total_rows: int
    validation_mode: str
    generated_at: str
    columns: list[ColumnValidation]
    duplicate_key_candidates: dict[str, int]
    proposed_schema_sql: str
    ready_for_transform: bool
    warnings: list[str]


def latest_profile(connection, dataset_name: str) -> dict[str, Any]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT profile_json
            FROM staging.dataset_profiles
            WHERE dataset_name = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (dataset_name,),
        )
        row = cur.fetchone()

    if not row:
        raise ValueError(
            f"No Stage 2 profile exists for dataset {dataset_name!r}."
        )

    payload = row[0]
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload)


def table_ref(table_name: str):
    return sql.SQL("staging.{}").format(sql.Identifier(table_name))


def count_invalid(
    connection,
    table_name: str,
    column_name: str,
    proposed_type: str,
    *,
    full_validation: bool,
    sample_limit: int,
) -> int:
    if proposed_type == "text":
        return 0

    col = sql.Identifier(column_name)
    null_values = sql.SQL(", ").join(
        sql.Literal(value) for value in NULL_LIKE
    )

    if proposed_type == "integer":
        invalid = sql.SQL("NOT ({0} ~ {1})").format(
            col,
            sql.Literal(INTEGER_REGEX),
        )
    elif proposed_type == "numeric":
        invalid = sql.SQL("NOT ({0} ~ {1})").format(
            col,
            sql.Literal(NUMERIC_REGEX),
        )
    elif proposed_type == "date":
        invalid = sql.SQL("NOT ({0} ~ {1})").format(
            col,
            sql.Literal(DATE_REGEX),
        )
    elif proposed_type == "boolean":
        invalid = sql.SQL(
            "lower(trim({0})) NOT IN ({1})"
        ).format(
            col,
            sql.SQL(", ").join(
                sql.Literal(value)
                for value in BOOLEAN_VALUES
            ),
        )
    else:
        return 0

    if full_validation:
        stmt = sql.SQL(
            """
            SELECT count(*)
            FROM {table}
            WHERE {col} IS NOT NULL
              AND lower(trim({col})) NOT IN ({null_values})
              AND {invalid}
            """
        ).format(
            table=table_ref(table_name),
            col=col,
            null_values=null_values,
            invalid=invalid,
        )
        params = ()
    else:
        stmt = sql.SQL(
            """
            SELECT count(*)
            FROM (
                SELECT {col}
                FROM {table}
                LIMIT %s
            ) s
            WHERE {col} IS NOT NULL
              AND lower(trim({col})) NOT IN ({null_values})
              AND {invalid}
            """
        ).format(
            table=table_ref(table_name),
            col=col,
            null_values=null_values,
            invalid=invalid,
        )
        params = (sample_limit,)

    with connection.cursor() as cur:
        cur.execute(stmt, params)
        return int(cur.fetchone()[0])


def count_duplicates(
    connection,
    table_name: str,
    column_name: str,
    *,
    full_validation: bool,
    sample_limit: int,
) -> int:
    col = sql.Identifier(column_name)

    if full_validation:
        stmt = sql.SQL(
            """
            SELECT COALESCE(SUM(c - 1), 0)
            FROM (
                SELECT {col}, count(*) AS c
                FROM {table}
                WHERE {col} IS NOT NULL
                  AND trim({col}) <> ''
                GROUP BY {col}
                HAVING count(*) > 1
            ) d
            """
        ).format(
            col=col,
            table=table_ref(table_name),
        )
        params = ()
    else:
        stmt = sql.SQL(
            """
            SELECT COALESCE(SUM(c - 1), 0)
            FROM (
                SELECT {col}, count(*) AS c
                FROM (
                    SELECT {col}
                    FROM {table}
                    LIMIT %s
                ) s
                WHERE {col} IS NOT NULL
                  AND trim({col}) <> ''
                GROUP BY {col}
                HAVING count(*) > 1
            ) d
            """
        ).format(
            col=col,
            table=table_ref(table_name),
        )
        params = (sample_limit,)

    with connection.cursor() as cur:
        cur.execute(stmt, params)
        return int(cur.fetchone()[0])


def postgres_type(likely_type: str, likely_role: str) -> str:
    if likely_role == "identifier":
        return "TEXT"

    return {
        "integer": "BIGINT",
        "numeric": "NUMERIC",
        "date": "DATE",
        "boolean": "BOOLEAN",
        "text": "TEXT",
    }.get(likely_type, "TEXT")


def proposed_schema_sql(
    dataset_name: str,
    columns: list[ColumnValidation],
) -> str:
    table_name = f"{sanitize_identifier(dataset_name)}_clean"[:60]

    defs = [
        "    _bundle_row_id BIGSERIAL PRIMARY KEY"
    ]

    for column in columns:
        defs.append(
            f'    "{column.column_name}" '
            f'{postgres_type(column.proposed_type, column.proposed_role)}'
        )

    defs.extend(
        [
            "    _source_file TEXT",
            "    _source_row BIGINT",
            "    _loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ]
    )

    return (
        "CREATE SCHEMA IF NOT EXISTS analytics;\n\n"
        f'CREATE TABLE analytics."{table_name}" (\n'
        + ",\n".join(defs)
        + "\n);"
    )


def save_report(connection, report: ValidationReport):
    payload = json.dumps(
        {
            "dataset_name": report.dataset_name,
            "staging_table": report.staging_table,
            "total_rows": report.total_rows,
            "validation_mode": report.validation_mode,
            "generated_at": report.generated_at,
            "columns": [asdict(c) for c in report.columns],
            "duplicate_key_candidates": report.duplicate_key_candidates,
            "proposed_schema_sql": report.proposed_schema_sql,
            "ready_for_transform": report.ready_for_transform,
            "warnings": report.warnings,
        },
        ensure_ascii=False,
    )

    connection.execute(
        """
        INSERT INTO staging.validation_reports (
            dataset_name,
            staging_table,
            validation_mode,
            ready_for_transform,
            report_json
        )
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (
            report.dataset_name,
            report.staging_table,
            report.validation_mode,
            report.ready_for_transform,
            payload,
        ),
    )


def validate_dataset(
    dataset_name: str,
    *,
    full_validation: bool = False,
    sample_limit: int = 50_000,
) -> ValidationReport:
    if sample_limit < 100:
        raise ValueError("sample_limit must be at least 100.")

    clean_dataset = sanitize_identifier(dataset_name)
    table_name = f"{clean_dataset}_raw"[:60]

    with get_ingest_connection() as connection:
        profile = latest_profile(connection, clean_dataset)

        column_results: list[ColumnValidation] = []
        duplicate_candidates: dict[str, int] = {}
        dataset_warnings: list[str] = []

        for column in profile.get("columns", []):
            name = str(column["column_name"])
            likely_type = str(column.get("likely_type", "text"))
            likely_role = str(column.get("likely_role", "dimension"))
            null_rate = float(column.get("null_rate", 0.0))
            rag_candidate = bool(column.get("rag_candidate", False))

            invalid_rows = count_invalid(
                connection,
                table_name,
                name,
                likely_type,
                full_validation=full_validation,
                sample_limit=sample_limit,
            )

            duplicate_rows = None
            if likely_role == "identifier":
                duplicate_rows = count_duplicates(
                    connection,
                    table_name,
                    name,
                    full_validation=full_validation,
                    sample_limit=sample_limit,
                )
                duplicate_candidates[name] = duplicate_rows

            warnings: list[str] = []

            if invalid_rows > 0:
                warnings.append(
                    f"{invalid_rows} rows do not match the proposed {likely_type} format."
                )

            if duplicate_rows is not None and duplicate_rows > 0:
                warnings.append(
                    f"{duplicate_rows} duplicate identifier values were detected."
                )

            if null_rate >= 0.30:
                warnings.append(
                    "High missing-value rate (30% or more)."
                )

            column_results.append(
                ColumnValidation(
                    column_name=name,
                    proposed_type=likely_type,
                    proposed_role=likely_role,
                    nullable=(null_rate > 0),
                    invalid_rows=invalid_rows,
                    duplicate_rows=duplicate_rows,
                    conversion_safe=(invalid_rows == 0),
                    rag_candidate=rag_candidate,
                    warnings=warnings,
                )
            )

        blocking = [
            c.column_name
            for c in column_results
            if not c.conversion_safe
        ]

        duplicate_ids = [
            name
            for name, count in duplicate_candidates.items()
            if count > 0
        ]

        if blocking:
            dataset_warnings.append(
                "Some proposed structured columns are not yet safe to convert."
            )

        if duplicate_ids:
            dataset_warnings.append(
                "Identifier candidates contain duplicates."
            )

        ready = not blocking and not duplicate_ids

        report = ValidationReport(
            dataset_name=clean_dataset,
            staging_table=f"staging.{table_name}",
            total_rows=int(profile.get("total_rows", 0)),
            validation_mode=(
                "full"
                if full_validation
                else f"sample:{sample_limit}"
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
            columns=column_results,
            duplicate_key_candidates=duplicate_candidates,
            proposed_schema_sql=proposed_schema_sql(
                clean_dataset,
                column_results,
            ),
            ready_for_transform=ready,
            warnings=dataset_warnings,
        )

        save_report(connection, report)
        connection.commit()

        return report


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    return {
        "dataset_name": report.dataset_name,
        "staging_table": report.staging_table,
        "total_rows": report.total_rows,
        "validation_mode": report.validation_mode,
        "generated_at": report.generated_at,
        "columns": [asdict(c) for c in report.columns],
        "duplicate_key_candidates": report.duplicate_key_candidates,
        "proposed_schema_sql": report.proposed_schema_sql,
        "ready_for_transform": report.ready_for_transform,
        "warnings": report.warnings,
    }

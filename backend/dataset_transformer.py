import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg import sql

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


NULL_LIKE = (
    "",
    "null",
    "none",
    "n/a",
    "na",
    "nan",
    "-",
)

INTEGER_REGEX = r"^[+-]?\d+$"
NUMERIC_REGEX = (
    r"^[₹$€£]?\s*[+-]?"
    r"(?:\d{1,3}(?:,\d{3})*|\d+)"
    r"(?:\.\d+)?$"
)
DATE_REGEX = (
    r"^(?:"
    r"\d{4}-\d{2}-\d{2}|"
    r"\d{2}/\d{2}/\d{4}|"
    r"\d{2}-\d{2}-\d{4}|"
    r"\d{4}/\d{2}/\d{2}"
    r")$"
)

TRUE_VALUES = (
    "true",
    "yes",
    "y",
    "1",
)

FALSE_VALUES = (
    "false",
    "no",
    "n",
    "0",
)


@dataclass(frozen=True)
class TransformationResult:
    job_id: int
    dataset_name: str
    source_table: str
    target_table: str
    rows_transformed: int
    rows_quarantined: int
    started_at: datetime
    finished_at: datetime


def latest_validation_report(
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
            f"No Stage 3 validation report exists for {dataset_name!r}."
        )

    payload = row[0]

    if isinstance(payload, str):
        payload = json.loads(payload)

    report = dict(payload)

    if not bool(
        report.get(
            "ready_for_transform",
            False,
        )
    ):
        raise ValueError(
            "The latest Stage 3 validation report is not ready for transformation."
        )

    return report


def target_table_name(
    dataset_name: str,
) -> str:
    return (
        f"{sanitize_identifier(dataset_name)}_clean"
    )[:60]


def source_table_name(
    dataset_name: str,
) -> str:
    return (
        f"{sanitize_identifier(dataset_name)}_raw"
    )[:60]


def postgres_type(
    proposed_type: str,
    proposed_role: str,
) -> str:
    if proposed_role == "identifier":
        return "TEXT"

    return {
        "integer": "BIGINT",
        "numeric": "NUMERIC",
        "date": "DATE",
        "boolean": "BOOLEAN",
        "text": "TEXT",
    }.get(
        proposed_type,
        "TEXT",
    )


def table_exists(
    connection,
    schema_name: str,
    table_name: str,
) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE
                    table_schema = %s
                    AND table_name = %s
            )
            """,
            (
                schema_name,
                table_name,
            ),
        )

        return bool(
            cur.fetchone()[0]
        )


def table_row_count(
    connection,
    schema_name: str,
    table_name: str,
) -> int:
    stmt = sql.SQL(
        "SELECT count(*) FROM {}.{}"
    ).format(
        sql.Identifier(
            schema_name
        ),
        sql.Identifier(
            table_name
        ),
    )

    with connection.cursor() as cur:
        cur.execute(stmt)
        return int(
            cur.fetchone()[0]
        )


def normalized_null_expression(
    column_name: str,
):
    column = sql.Identifier(
        column_name
    )

    return sql.SQL(
        """
        CASE
            WHEN {col} IS NULL
              OR lower(trim({col})) IN ({null_values})
            THEN NULL
            ELSE trim({col})
        END
        """
    ).format(
        col=column,
        null_values=sql.SQL(", ").join(
            sql.Literal(value)
            for value in NULL_LIKE
        ),
    )


def cast_expression(
    column_name: str,
    proposed_type: str,
    proposed_role: str,
):
    raw = normalized_null_expression(
        column_name
    )

    if proposed_role == "identifier":
        return raw

    if proposed_type == "integer":
        return sql.SQL(
            "({raw})::BIGINT"
        ).format(
            raw=raw
        )

    if proposed_type == "numeric":
        return sql.SQL(
            """
            NULLIF(
                regexp_replace(
                    {raw},
                    '[₹$€£,\\s]',
                    '',
                    'g'
                ),
                ''
            )::NUMERIC
            """
        ).format(
            raw=raw
        )

    if proposed_type == "boolean":
        column = sql.Identifier(
            column_name
        )

        return sql.SQL(
            """
            CASE
                WHEN {raw} IS NULL
                THEN NULL
                WHEN lower(trim({col})) IN ({true_values})
                THEN TRUE
                WHEN lower(trim({col})) IN ({false_values})
                THEN FALSE
                ELSE NULL
            END
            """
        ).format(
            raw=raw,
            col=column,
            true_values=sql.SQL(", ").join(
                sql.Literal(value)
                for value in TRUE_VALUES
            ),
            false_values=sql.SQL(", ").join(
                sql.Literal(value)
                for value in FALSE_VALUES
            ),
        )

    if proposed_type == "date":
        column = sql.Identifier(
            column_name
        )

        return sql.SQL(
            """
            CASE
                WHEN {raw} IS NULL
                THEN NULL
                WHEN trim({col}) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
                THEN to_date(trim({col}), 'YYYY-MM-DD')
                WHEN trim({col}) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
                THEN to_date(trim({col}), 'DD/MM/YYYY')
                WHEN trim({col}) ~ '^\\d{{2}}-\\d{{2}}-\\d{{4}}$'
                THEN to_date(trim({col}), 'DD-MM-YYYY')
                WHEN trim({col}) ~ '^\\d{{4}}/\\d{{2}}/\\d{{2}}$'
                THEN to_date(trim({col}), 'YYYY/MM/DD')
                ELSE NULL
            END
            """
        ).format(
            raw=raw,
            col=column,
        )

    return raw


def invalid_condition(
    column_name: str,
    proposed_type: str,
    proposed_role: str,
):
    if (
        proposed_role == "identifier"
        or proposed_type == "text"
    ):
        return sql.SQL("FALSE")

    column = sql.Identifier(
        column_name
    )

    non_null = sql.SQL(
        """
        {col} IS NOT NULL
        AND lower(trim({col})) NOT IN ({null_values})
        """
    ).format(
        col=column,
        null_values=sql.SQL(", ").join(
            sql.Literal(value)
            for value in NULL_LIKE
        ),
    )

    if proposed_type == "integer":
        invalid = sql.SQL(
            "NOT ({col} ~ {pattern})"
        ).format(
            col=column,
            pattern=sql.Literal(
                INTEGER_REGEX
            ),
        )

    elif proposed_type == "numeric":
        invalid = sql.SQL(
            "NOT ({col} ~ {pattern})"
        ).format(
            col=column,
            pattern=sql.Literal(
                NUMERIC_REGEX
            ),
        )

    elif proposed_type == "date":
        invalid = sql.SQL(
            "NOT ({col} ~ {pattern})"
        ).format(
            col=column,
            pattern=sql.Literal(
                DATE_REGEX
            ),
        )

    elif proposed_type == "boolean":
        invalid = sql.SQL(
            """
            lower(trim({col})) NOT IN ({allowed})
            """
        ).format(
            col=column,
            allowed=sql.SQL(", ").join(
                sql.Literal(value)
                for value in (
                    *TRUE_VALUES,
                    *FALSE_VALUES,
                )
            ),
        )

    else:
        return sql.SQL("FALSE")

    return sql.SQL(
        "(({non_null}) AND ({invalid}))"
    ).format(
        non_null=non_null,
        invalid=invalid,
    )


def create_target_table(
    connection,
    target_table: str,
    columns: list[dict[str, Any]],
):
    definitions = [
        sql.SQL(
            "_bundle_row_id BIGSERIAL PRIMARY KEY"
        )
    ]

    for column in columns:
        name = str(
            column["column_name"]
        )

        pg_type = postgres_type(
            str(
                column.get(
                    "proposed_type",
                    "text",
                )
            ),
            str(
                column.get(
                    "proposed_role",
                    "dimension",
                )
            ),
        )

        definitions.append(
            sql.SQL("{} {}").format(
                sql.Identifier(name),
                sql.SQL(pg_type),
            )
        )

    definitions.extend(
        [
            sql.SQL(
                "_source_file TEXT NOT NULL"
            ),
            sql.SQL(
                "_source_row BIGINT NOT NULL"
            ),
            sql.SQL(
                "_loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ),
        ]
    )

    stmt = sql.SQL(
        """
        CREATE TABLE analytics.{} (
            {}
        )
        """
    ).format(
        sql.Identifier(
            target_table
        ),
        sql.SQL(", ").join(
            definitions
        ),
    )

    connection.execute(stmt)


def create_useful_indexes(
    connection,
    target_table: str,
    columns: list[dict[str, Any]],
):
    for column in columns:
        role = str(
            column.get(
                "proposed_role",
                "",
            )
        )

        if role not in {
            "identifier",
            "date_dimension",
            "category",
        }:
            continue

        name = str(
            column["column_name"]
        )

        index_name = (
            f"{target_table}_{name}_idx"
        )[:60]

        stmt = sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS {}
            ON analytics.{} ({})
            """
        ).format(
            sql.Identifier(
                index_name
            ),
            sql.Identifier(
                target_table
            ),
            sql.Identifier(
                name
            ),
        )

        connection.execute(stmt)


def create_job(
    connection,
    dataset_name: str,
    source_table: str,
    target_table: str,
) -> int:
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staging.transformation_jobs (
                dataset_name,
                source_table,
                target_table,
                status
            )
            VALUES (%s, %s, %s, 'running')
            RETURNING id
            """,
            (
                dataset_name,
                source_table,
                target_table,
            ),
        )

        return int(
            cur.fetchone()[0]
        )


def finish_job(
    connection,
    job_id: int,
    status: str,
    rows_transformed: int,
    rows_quarantined: int,
    error_message: str | None = None,
):
    connection.execute(
        """
        UPDATE staging.transformation_jobs
        SET
            status = %s,
            rows_transformed = %s,
            rows_quarantined = %s,
            error_message = %s,
            finished_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (
            status,
            rows_transformed,
            rows_quarantined,
            error_message,
            job_id,
        ),
    )


def transform_dataset(
    dataset_name: str,
    *,
    replace_existing: bool = False,
) -> TransformationResult:
    clean_dataset = sanitize_identifier(
        dataset_name
    )

    source_table = source_table_name(
        clean_dataset
    )

    target_table = target_table_name(
        clean_dataset
    )

    started_at = datetime.now(
        timezone.utc
    )

    with get_ingest_connection() as connection:
        connection.execute(
            "CREATE SCHEMA IF NOT EXISTS analytics"
        )

        report = latest_validation_report(
            connection,
            clean_dataset,
        )

        columns = list(
            report.get(
                "columns",
                [],
            )
        )

        if not columns:
            raise ValueError(
                "The validation report contains no columns."
            )

        if not table_exists(
            connection,
            "staging",
            source_table,
        ):
            raise ValueError(
                f"staging.{source_table} does not exist."
            )

        if table_exists(
            connection,
            "analytics",
            target_table,
        ):
            existing_rows = table_row_count(
                connection,
                "analytics",
                target_table,
            )

            if not replace_existing:
                raise ValueError(
                    f"analytics.{target_table} already exists "
                    f"with {existing_rows:,} rows. "
                    "Use --replace only when you intentionally want to rebuild it."
                )

            connection.execute(
                sql.SQL(
                    "DROP TABLE analytics.{}"
                ).format(
                    sql.Identifier(
                        target_table
                    )
                )
            )

        create_target_table(
            connection,
            target_table,
            columns,
        )

        job_id = create_job(
            connection,
            clean_dataset,
            f"staging.{source_table}",
            f"analytics.{target_table}",
        )

        connection.commit()

        invalid_conditions = [
            invalid_condition(
                str(column["column_name"]),
                str(
                    column.get(
                        "proposed_type",
                        "text",
                    )
                ),
                str(
                    column.get(
                        "proposed_role",
                        "dimension",
                    )
                ),
            )
            for column in columns
        ]

        any_invalid = sql.SQL(" OR ").join(
            invalid_conditions
        )

        try:
            quarantine_insert = sql.SQL(
                """
                INSERT INTO staging.quarantined_rows (
                    dataset_name,
                    source_table,
                    source_file,
                    source_row,
                    raw_record,
                    reason
                )
                SELECT
                    %s,
                    %s,
                    raw._source_file,
                    raw._source_row,
                    to_jsonb(raw),
                    %s
                FROM staging.{} AS raw
                WHERE {}
                """
            ).format(
                sql.Identifier(
                    source_table
                ),
                any_invalid,
            )

            with connection.cursor() as cur:
                cur.execute(
                    quarantine_insert,
                    (
                        clean_dataset,
                        f"staging.{source_table}",
                        (
                            "One or more values did not match "
                            "the approved Stage 3 conversion rules."
                        ),
                    ),
                )

                rows_quarantined = (
                    cur.rowcount
                    if cur.rowcount >= 0
                    else 0
                )

            target_columns = [
                sql.Identifier(
                    str(
                        column[
                            "column_name"
                        ]
                    )
                )
                for column in columns
            ]

            target_columns.extend(
                [
                    sql.Identifier(
                        "_source_file"
                    ),
                    sql.Identifier(
                        "_source_row"
                    ),
                ]
            )

            expressions = [
                cast_expression(
                    str(
                        column[
                            "column_name"
                        ]
                    ),
                    str(
                        column.get(
                            "proposed_type",
                            "text",
                        )
                    ),
                    str(
                        column.get(
                            "proposed_role",
                            "dimension",
                        )
                    ),
                )
                for column in columns
            ]

            expressions.extend(
                [
                    sql.Identifier(
                        "_source_file"
                    ),
                    sql.Identifier(
                        "_source_row"
                    ),
                ]
            )

            insert_stmt = sql.SQL(
                """
                INSERT INTO analytics.{} ({})
                SELECT {}
                FROM staging.{} AS raw
                WHERE NOT ({})
                """
            ).format(
                sql.Identifier(
                    target_table
                ),
                sql.SQL(", ").join(
                    target_columns
                ),
                sql.SQL(", ").join(
                    expressions
                ),
                sql.Identifier(
                    source_table
                ),
                any_invalid,
            )

            with connection.cursor() as cur:
                cur.execute(
                    insert_stmt
                )

                rows_transformed = (
                    cur.rowcount
                    if cur.rowcount >= 0
                    else 0
                )

            create_useful_indexes(
                connection,
                target_table,
                columns,
            )

            finish_job(
                connection,
                job_id,
                "completed",
                rows_transformed,
                rows_quarantined,
            )

            connection.commit()

        except Exception as exc:
            connection.rollback()

            finish_job(
                connection,
                job_id,
                "failed",
                0,
                0,
                str(exc)[:1000],
            )

            connection.commit()
            raise

    finished_at = datetime.now(
        timezone.utc
    )

    return TransformationResult(
        job_id=job_id,
        dataset_name=clean_dataset,
        source_table=(
            f"staging.{source_table}"
        ),
        target_table=(
            f"analytics.{target_table}"
        ),
        rows_transformed=(
            rows_transformed
        ),
        rows_quarantined=(
            rows_quarantined
        ),
        started_at=started_at,
        finished_at=finished_at,
    )

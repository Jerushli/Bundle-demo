import json
import math
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from psycopg import sql

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


NULL_LIKE = {
    "",
    "null",
    "none",
    "n/a",
    "na",
    "nan",
    "-",
}

TRUE_LIKE = {
    "true",
    "yes",
    "y",
    "1",
}

FALSE_LIKE = {
    "false",
    "no",
    "n",
    "0",
}

DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    re.compile(r"^\d{4}/\d{2}/\d{2}$"),
]

INTEGER_PATTERN = re.compile(
    r"^[+-]?\d+$"
)

DECIMAL_PATTERN = re.compile(
    r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$"
)

CURRENCY_PATTERN = re.compile(
    r"^[₹$€£]?\s*[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?$"
)

ID_NAME_HINTS = (
    "_id",
    "id",
    "code",
    "number",
    "no",
    "key",
)

TEXT_NAME_HINTS = (
    "note",
    "notes",
    "comment",
    "comments",
    "description",
    "details",
    "detail",
    "summary",
    "reason",
    "feedback",
    "message",
    "text",
)


@dataclass
class ColumnProfile:
    column_name: str
    sample_rows: int
    non_null_rows: int
    null_rows: int
    null_rate: float
    distinct_sample_values: int
    distinct_ratio: float
    avg_length: float
    max_length: int
    likely_type: str
    confidence: float
    likely_role: str
    rag_candidate: bool
    example_values: list[str]
    notes: list[str]


@dataclass
class DatasetProfile:
    dataset_name: str
    staging_table: str
    total_rows: int
    sample_rows: int
    column_count: int
    generated_at: str
    columns: list[ColumnProfile]
    summary: dict[str, Any]


def is_null_like(value: Any) -> bool:
    if value is None:
        return True

    return str(value).strip().lower() in NULL_LIKE


def clean_numeric(value: str) -> str:
    return (
        value.strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .strip()
    )


def looks_like_integer(value: str) -> bool:
    return bool(
        INTEGER_PATTERN.fullmatch(
            clean_numeric(value)
        )
    )


def looks_like_decimal(value: str) -> bool:
    cleaned = clean_numeric(value)

    return bool(
        DECIMAL_PATTERN.fullmatch(
            cleaned
        )
    )


def looks_like_currency(value: str) -> bool:
    return bool(
        CURRENCY_PATTERN.fullmatch(
            value.strip()
        )
    )


def looks_like_boolean(value: str) -> bool:
    normalized = value.strip().lower()

    return (
        normalized in TRUE_LIKE
        or normalized in FALSE_LIKE
    )


def looks_like_date(value: str) -> bool:
    candidate = value.strip()

    return any(
        pattern.fullmatch(candidate)
        for pattern in DATE_PATTERNS
    )


def ratio(
    matches: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return matches / total


def infer_likely_type(
    values: list[str],
) -> tuple[str, float, list[str]]:
    if not values:
        return (
            "text",
            0.0,
            ["No non-null sample values were available."],
        )

    total = len(values)

    boolean_ratio = ratio(
        sum(
            1
            for value in values
            if looks_like_boolean(value)
        ),
        total,
    )

    date_ratio = ratio(
        sum(
            1
            for value in values
            if looks_like_date(value)
        ),
        total,
    )

    integer_ratio = ratio(
        sum(
            1
            for value in values
            if looks_like_integer(value)
        ),
        total,
    )

    decimal_ratio = ratio(
        sum(
            1
            for value in values
            if looks_like_decimal(value)
        ),
        total,
    )

    currency_ratio = ratio(
        sum(
            1
            for value in values
            if looks_like_currency(value)
        ),
        total,
    )

    candidates = [
        ("boolean", boolean_ratio),
        ("date", date_ratio),
        ("integer", integer_ratio),
        ("numeric", max(decimal_ratio, currency_ratio)),
    ]

    candidates.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    likely_type, confidence = candidates[0]

    if confidence < 0.90:
        return (
            "text",
            round(1.0 - confidence, 4),
            [
                "Values are mixed or do not consistently match a supported structured type."
            ],
        )

    notes: list[str] = []

    if (
        likely_type == "numeric"
        and currency_ratio >= 0.90
    ):
        notes.append(
            "Values appear numeric and may include currency symbols or separators."
        )

    return (
        likely_type,
        round(confidence, 4),
        notes,
    )


def infer_role(
    column_name: str,
    values: list[str],
    likely_type: str,
    distinct_ratio: float,
    avg_length: float,
) -> tuple[str, bool, list[str]]:
    name = column_name.lower()
    notes: list[str] = []

    if (
        name == "id"
        or name.endswith("_id")
        or any(
            name.endswith(f"_{hint}")
            for hint in ("code", "key")
        )
    ):
        if distinct_ratio >= 0.80:
            return (
                "identifier",
                False,
                [
                    "Column name and high uniqueness suggest an identifier."
                ],
            )

    if likely_type == "date":
        return (
            "date_dimension",
            False,
            [],
        )

    if likely_type in {
        "integer",
        "numeric",
    }:
        return (
            "measure",
            False,
            [],
        )

    if likely_type == "boolean":
        return (
            "flag",
            False,
            [],
        )

    text_hint = any(
        hint in name
        for hint in TEXT_NAME_HINTS
    )

    rag_candidate = (
        likely_type == "text"
        and (
            text_hint
            or avg_length >= 80
        )
    )

    if rag_candidate:
        notes.append(
            "Long or descriptive text may be useful for RAG indexing after access controls are applied."
        )

        return (
            "free_text",
            True,
            notes,
        )

    if (
        distinct_ratio <= 0.20
        and values
    ):
        return (
            "category",
            False,
            [],
        )

    if distinct_ratio >= 0.80:
        return (
            "high_cardinality_text",
            False,
            [],
        )

    return (
        "dimension",
        False,
        [],
    )


def get_table_columns(
    connection,
    table_name: str,
) -> list[str]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = 'staging'
                AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )

        columns = [
            str(row[0])
            for row in cur.fetchall()
        ]

    return [
        column
        for column in columns
        if not column.startswith("_")
    ]


def get_total_rows(
    connection,
    table_name: str,
) -> int:
    statement = sql.SQL(
        "SELECT count(*) FROM staging.{}"
    ).format(
        sql.Identifier(table_name)
    )

    with connection.cursor() as cur:
        cur.execute(statement)
        return int(cur.fetchone()[0])


def fetch_sample_rows(
    connection,
    table_name: str,
    columns: list[str],
    sample_size: int,
) -> list[tuple]:
    statement = sql.SQL(
        "SELECT {} FROM staging.{} LIMIT %s"
    ).format(
        sql.SQL(", ").join(
            sql.Identifier(column)
            for column in columns
        ),
        sql.Identifier(table_name),
    )

    with connection.cursor() as cur:
        cur.execute(
            statement,
            (sample_size,),
        )

        return cur.fetchall()


def profile_column(
    column_name: str,
    raw_values: Iterable[Any],
    sample_rows: int,
) -> ColumnProfile:
    non_null_values: list[str] = []

    for value in raw_values:
        if not is_null_like(value):
            non_null_values.append(
                str(value).strip()
            )

    non_null_rows = len(non_null_values)
    null_rows = sample_rows - non_null_rows
    null_rate = (
        null_rows / sample_rows
        if sample_rows
        else 0.0
    )

    distinct_values = set(
        non_null_values
    )

    distinct_count = len(
        distinct_values
    )

    distinct_ratio = (
        distinct_count / non_null_rows
        if non_null_rows
        else 0.0
    )

    lengths = [
        len(value)
        for value in non_null_values
    ]

    avg_length = (
        sum(lengths) / len(lengths)
        if lengths
        else 0.0
    )

    max_length = (
        max(lengths)
        if lengths
        else 0
    )

    likely_type, confidence, type_notes = (
        infer_likely_type(
            non_null_values
        )
    )

    likely_role, rag_candidate, role_notes = (
        infer_role(
            column_name,
            non_null_values,
            likely_type,
            distinct_ratio,
            avg_length,
        )
    )

    examples: list[str] = []

    for value in non_null_values:
        if value not in examples:
            examples.append(
                value[:180]
            )

        if len(examples) >= 5:
            break

    return ColumnProfile(
        column_name=column_name,
        sample_rows=sample_rows,
        non_null_rows=non_null_rows,
        null_rows=null_rows,
        null_rate=round(
            null_rate,
            4,
        ),
        distinct_sample_values=distinct_count,
        distinct_ratio=round(
            distinct_ratio,
            4,
        ),
        avg_length=round(
            avg_length,
            2,
        ),
        max_length=max_length,
        likely_type=likely_type,
        confidence=confidence,
        likely_role=likely_role,
        rag_candidate=rag_candidate,
        example_values=examples,
        notes=[
            *type_notes,
            *role_notes,
        ],
    )


def build_summary(
    columns: list[ColumnProfile],
) -> dict[str, Any]:
    type_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}

    for column in columns:
        type_counts[column.likely_type] = (
            type_counts.get(
                column.likely_type,
                0,
            )
            + 1
        )

        role_counts[column.likely_role] = (
            role_counts.get(
                column.likely_role,
                0,
            )
            + 1
        )

    rag_candidates = [
        column.column_name
        for column in columns
        if column.rag_candidate
    ]

    high_missing = [
        column.column_name
        for column in columns
        if column.null_rate >= 0.30
    ]

    identifiers = [
        column.column_name
        for column in columns
        if column.likely_role == "identifier"
    ]

    measures = [
        column.column_name
        for column in columns
        if column.likely_role == "measure"
    ]

    categories = [
        column.column_name
        for column in columns
        if column.likely_role == "category"
    ]

    return {
        "type_counts": type_counts,
        "role_counts": role_counts,
        "identifier_candidates": identifiers,
        "measure_candidates": measures,
        "category_candidates": categories,
        "rag_candidates": rag_candidates,
        "high_missing_columns": high_missing,
    }


def save_profile(
    connection,
    profile: DatasetProfile,
):
    payload = json.dumps(
        {
            "dataset_name": profile.dataset_name,
            "staging_table": profile.staging_table,
            "total_rows": profile.total_rows,
            "sample_rows": profile.sample_rows,
            "column_count": profile.column_count,
            "generated_at": profile.generated_at,
            "columns": [
                asdict(column)
                for column in profile.columns
            ],
            "summary": profile.summary,
        },
        ensure_ascii=False,
    )

    connection.execute(
        """
        INSERT INTO staging.dataset_profiles (
            dataset_name,
            staging_table,
            total_rows,
            sample_rows,
            column_count,
            profile_json
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            profile.dataset_name,
            profile.staging_table,
            profile.total_rows,
            profile.sample_rows,
            profile.column_count,
            payload,
        ),
    )


def profile_dataset(
    dataset_name: str,
    sample_size: int = 50_000,
) -> DatasetProfile:
    clean_dataset = sanitize_identifier(
        dataset_name
    )

    table_name = (
        f"{clean_dataset}_raw"
    )[:60]

    if sample_size < 100:
        raise ValueError(
            "sample_size must be at least 100."
        )

    with get_ingest_connection() as connection:
        columns = get_table_columns(
            connection,
            table_name,
        )

        if not columns:
            raise ValueError(
                f"staging.{table_name} does not exist or has no source columns."
            )

        total_rows = get_total_rows(
            connection,
            table_name,
        )

        rows = fetch_sample_rows(
            connection,
            table_name,
            columns,
            sample_size,
        )

        sample_rows = len(rows)

        profiles: list[ColumnProfile] = []

        for index, column in enumerate(
            columns
        ):
            profiles.append(
                profile_column(
                    column_name=column,
                    raw_values=(
                        row[index]
                        for row in rows
                    ),
                    sample_rows=sample_rows,
                )
            )

        summary = build_summary(
            profiles
        )

        profile = DatasetProfile(
            dataset_name=clean_dataset,
            staging_table=(
                f"staging.{table_name}"
            ),
            total_rows=total_rows,
            sample_rows=sample_rows,
            column_count=len(columns),
            generated_at=datetime.now(
                timezone.utc
            ).isoformat(),
            columns=profiles,
            summary=summary,
        )

        save_profile(
            connection,
            profile,
        )

        connection.commit()

        return profile


def profile_to_dict(
    profile: DatasetProfile,
) -> dict[str, Any]:
    return {
        "dataset_name": profile.dataset_name,
        "staging_table": profile.staging_table,
        "total_rows": profile.total_rows,
        "sample_rows": profile.sample_rows,
        "column_count": profile.column_count,
        "generated_at": profile.generated_at,
        "columns": [
            asdict(column)
            for column in profile.columns
        ],
        "summary": profile.summary,
    }

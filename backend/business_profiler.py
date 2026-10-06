import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg import sql

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


PRIMARY_MEASURE_PRIORITY = (
    "profit",
    "revenue",
    "sales",
    "amount",
    "value",
    "gross_sales",
    "net_sales",
    "units_sold",
)

CATEGORY_PRIORITY = (
    "region",
    "country",
    "segment",
    "product",
    "category",
    "department",
    "channel",
)

MAX_MEASURES = 12
MAX_CATEGORIES = 8
TOP_N = 5


@dataclass
class MeasureStats:
    column_name: str
    total: float | None
    average: float | None
    minimum: float | None
    maximum: float | None
    non_null_rows: int


@dataclass
class CategoryBreakdown:
    category_column: str
    measure_column: str
    values: list[dict[str, Any]]


@dataclass
class BusinessProfile:
    dataset_name: str
    analytics_table: str
    total_rows: int
    date_ranges: dict[str, dict[str, str | None]]
    measures: list[MeasureStats]
    category_breakdowns: list[CategoryBreakdown]
    primary_measure: str | None
    quick_summary: str
    suggested_questions: list[str]
    generated_at: str


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


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
        return json.loads(payload)

    return dict(payload)


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


def clean_table_name(
    dataset_name: str,
) -> str:
    return (
        f"{sanitize_identifier(dataset_name)}_clean"
    )[:60]


def select_profile_columns(
    report: dict[str, Any],
) -> tuple[
    list[str],
    list[str],
    list[str],
]:
    measure_columns: list[str] = []
    category_columns: list[str] = []
    date_columns: list[str] = []

    for column in report.get(
        "columns",
        [],
    ):
        name = str(
            column.get(
                "column_name",
                "",
            )
        )

        role = str(
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

        if (
            role == "measure"
            and proposed_type in {
                "integer",
                "numeric",
            }
        ):
            measure_columns.append(
                name
            )

        if role in {
            "category",
            "dimension",
        }:
            category_columns.append(
                name
            )

        if (
            role == "date_dimension"
            or proposed_type == "date"
        ):
            date_columns.append(
                name
            )

    def priority_sort(
        values: list[str],
        priority: tuple[str, ...],
    ) -> list[str]:
        rank = {
            name: index
            for index, name
            in enumerate(priority)
        }

        return sorted(
            values,
            key=lambda value: (
                rank.get(
                    value.lower(),
                    10_000,
                ),
                value.lower(),
            ),
        )

    measure_columns = priority_sort(
        measure_columns,
        PRIMARY_MEASURE_PRIORITY,
    )[:MAX_MEASURES]

    category_columns = priority_sort(
        category_columns,
        CATEGORY_PRIORITY,
    )[:MAX_CATEGORIES]

    return (
        measure_columns,
        category_columns,
        date_columns,
    )


def get_total_rows(
    connection,
    table_name: str,
) -> int:
    statement = sql.SQL(
        "SELECT count(*) FROM analytics.{}"
    ).format(
        sql.Identifier(
            table_name
        )
    )

    with connection.cursor() as cur:
        cur.execute(
            statement
        )

        return int(
            cur.fetchone()[0]
        )


def get_measure_stats(
    connection,
    table_name: str,
    column_name: str,
) -> MeasureStats:
    column = sql.Identifier(
        column_name
    )

    statement = sql.SQL(
        """
        SELECT
            SUM({column}),
            AVG({column}),
            MIN({column}),
            MAX({column}),
            count({column})
        FROM analytics.{table}
        """
    ).format(
        column=column,
        table=sql.Identifier(
            table_name
        ),
    )

    with connection.cursor() as cur:
        cur.execute(statement)
        row = cur.fetchone()

    return MeasureStats(
        column_name=column_name,
        total=(
            float(row[0])
            if row[0] is not None
            else None
        ),
        average=(
            float(row[1])
            if row[1] is not None
            else None
        ),
        minimum=(
            float(row[2])
            if row[2] is not None
            else None
        ),
        maximum=(
            float(row[3])
            if row[3] is not None
            else None
        ),
        non_null_rows=int(
            row[4]
        ),
    )


def get_date_range(
    connection,
    table_name: str,
    column_name: str,
) -> dict[str, str | None]:
    column = sql.Identifier(
        column_name
    )

    statement = sql.SQL(
        """
        SELECT
            MIN({column}),
            MAX({column})
        FROM analytics.{table}
        """
    ).format(
        column=column,
        table=sql.Identifier(
            table_name
        ),
    )

    with connection.cursor() as cur:
        cur.execute(statement)
        row = cur.fetchone()

    return {
        "minimum": (
            row[0].isoformat()
            if row[0] is not None
            else None
        ),
        "maximum": (
            row[1].isoformat()
            if row[1] is not None
            else None
        ),
    }


def get_top_category_values(
    connection,
    table_name: str,
    category_column: str,
    measure_column: str,
    top_n: int = TOP_N,
) -> CategoryBreakdown:
    category = sql.Identifier(
        category_column
    )

    measure = sql.Identifier(
        measure_column
    )

    statement = sql.SQL(
        """
        SELECT
            {category},
            SUM({measure}) AS total_value,
            count(*) AS row_count
        FROM analytics.{table}
        WHERE {category} IS NOT NULL
        GROUP BY {category}
        ORDER BY
            total_value DESC NULLS LAST,
            row_count DESC,
            {category}
        LIMIT %s
        """
    ).format(
        category=category,
        measure=measure,
        table=sql.Identifier(
            table_name
        ),
    )

    with connection.cursor() as cur:
        cur.execute(
            statement,
            (top_n,),
        )

        rows = cur.fetchall()

    values = [
        {
            "name": str(row[0]),
            "total": (
                float(row[1])
                if row[1] is not None
                else None
            ),
            "row_count": int(
                row[2]
            ),
        }
        for row in rows
    ]

    return CategoryBreakdown(
        category_column=(
            category_column
        ),
        measure_column=(
            measure_column
        ),
        values=values,
    )


def choose_primary_measure(
    measure_columns: list[str],
    override: str | None,
) -> str | None:
    if override:
        if override not in measure_columns:
            raise ValueError(
                f"Primary measure {override!r} is not a validated measure column."
            )

        return override

    lowered = {
        value.lower(): value
        for value in measure_columns
    }

    for candidate in PRIMARY_MEASURE_PRIORITY:
        if candidate in lowered:
            return lowered[
                candidate
            ]

    if measure_columns:
        return measure_columns[0]

    return None


def pretty_number(
    value: float | None,
) -> str:
    if value is None:
        return "n/a"

    absolute = abs(
        value
    )

    if absolute >= 1_000_000_000:
        return (
            f"{value / 1_000_000_000:,.2f}B"
        )

    if absolute >= 1_000_000:
        return (
            f"{value / 1_000_000:,.2f}M"
        )

    if absolute >= 1_000:
        return (
            f"{value / 1_000:,.2f}K"
        )

    return f"{value:,.2f}"


def build_quick_summary(
    *,
    total_rows: int,
    primary_measure: str | None,
    measures: list[MeasureStats],
    category_breakdowns: list[CategoryBreakdown],
    date_ranges: dict[
        str,
        dict[
            str,
            str | None,
        ],
    ],
) -> str:
    parts: list[str] = []

    if date_ranges:
        first_date_name = next(
            iter(
                date_ranges
            )
        )

        date_range = date_ranges[
            first_date_name
        ]

        if (
            date_range.get(
                "minimum"
            )
            and date_range.get(
                "maximum"
            )
        ):
            parts.append(
                f"The dataset contains {total_rows:,} rows covering "
                f"{date_range['minimum']} to {date_range['maximum']}."
            )
        else:
            parts.append(
                f"The dataset contains {total_rows:,} rows."
            )
    else:
        parts.append(
            f"The dataset contains {total_rows:,} rows."
        )

    primary_stats = next(
        (
            measure
            for measure in measures
            if measure.column_name
            == primary_measure
        ),
        None,
    )

    if (
        primary_measure
        and primary_stats
        and primary_stats.total
        is not None
    ):
        parts.append(
            f"Total {primary_measure.replace('_', ' ')} is "
            f"{pretty_number(primary_stats.total)}."
        )

    primary_breakdowns = [
        breakdown
        for breakdown
        in category_breakdowns
        if (
            breakdown.measure_column
            == primary_measure
            and breakdown.values
        )
    ]

    if primary_breakdowns:
        preferred = primary_breakdowns[0]
        leader = preferred.values[0]

        parts.append(
            f"{leader['name']} is the strongest observed "
            f"{preferred.category_column.replace('_', ' ')} by "
            f"{preferred.measure_column.replace('_', ' ')}, "
            f"with {pretty_number(leader['total'])}."
        )

        if len(
            preferred.values
        ) >= 2:
            second = preferred.values[1]

            if (
                leader.get(
                    "total"
                )
                is not None
                and second.get(
                    "total"
                )
                is not None
                and leader[
                    "total"
                ] > second[
                    "total"
                ]
            ):
                gap = (
                    leader[
                        "total"
                    ]
                    - second[
                        "total"
                    ]
                )

                parts.append(
                    f"It leads the next {preferred.category_column.replace('_', ' ')} "
                    f"by approximately {pretty_number(gap)}."
                )

        parts.append(
            "This makes it a strong candidate for deeper review, "
            "but an investment decision should also consider profitability, "
            "cost, capacity, risk, and relevant company documents."
        )

    if len(parts) == 1:
        parts.append(
            "More detailed business conclusions require at least one validated numeric measure."
        )

    return " ".join(
        parts
    )


def build_suggested_questions(
    primary_measure: str | None,
    categories: list[str],
    measures: list[str],
) -> list[str]:
    suggestions: list[str] = []

    if (
        primary_measure
        and categories
    ):
        suggestions.append(
            f"Which {categories[0].replace('_', ' ')} has the highest "
            f"{primary_measure.replace('_', ' ')}?"
        )

        suggestions.append(
            f"Compare {primary_measure.replace('_', ' ')} across "
            f"{categories[0].replace('_', ' ')}."
        )

    if (
        "profit" in [
            measure.lower()
            for measure in measures
        ]
        and "sales" in [
            measure.lower()
            for measure in measures
        ]
    ):
        suggestions.append(
            "Which area has strong sales but weak profit?"
        )

    suggestions.append(
        "What are the most important patterns in this dataset?"
    )

    return suggestions[:4]


def save_profile(
    connection,
    profile: BusinessProfile,
):
    payload = json.dumps(
        {
            "dataset_name": profile.dataset_name,
            "analytics_table": (
                profile.analytics_table
            ),
            "total_rows": profile.total_rows,
            "date_ranges": profile.date_ranges,
            "measures": [
                asdict(
                    measure
                )
                for measure
                in profile.measures
            ],
            "category_breakdowns": [
                asdict(
                    breakdown
                )
                for breakdown
                in profile.category_breakdowns
            ],
            "primary_measure": (
                profile.primary_measure
            ),
            "quick_summary": (
                profile.quick_summary
            ),
            "suggested_questions": (
                profile.suggested_questions
            ),
            "generated_at": (
                profile.generated_at
            ),
        },
        ensure_ascii=False,
        default=json_safe,
    )

    connection.execute(
        """
        INSERT INTO analytics.dataset_business_profiles (
            dataset_name,
            analytics_table,
            total_rows,
            primary_measure,
            quick_summary,
            profile_json
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            profile.dataset_name,
            profile.analytics_table,
            profile.total_rows,
            profile.primary_measure,
            profile.quick_summary,
            payload,
        ),
    )


def profile_business_dataset(
    dataset_name: str,
    *,
    primary_measure_override: str | None = None,
) -> BusinessProfile:
    clean_dataset = sanitize_identifier(
        dataset_name
    )

    table_name = clean_table_name(
        clean_dataset
    )

    with get_ingest_connection() as connection:
        if not table_exists(
            connection,
            "analytics",
            table_name,
        ):
            raise ValueError(
                f"analytics.{table_name} does not exist. Run Stage 4 first."
            )

        report = latest_validation_report(
            connection,
            clean_dataset,
        )

        (
            measure_columns,
            category_columns,
            date_columns,
        ) = select_profile_columns(
            report
        )

        primary_measure = choose_primary_measure(
            measure_columns,
            primary_measure_override,
        )

        total_rows = get_total_rows(
            connection,
            table_name,
        )

        measures = [
            get_measure_stats(
                connection,
                table_name,
                measure,
            )
            for measure
            in measure_columns
        ]

        date_ranges = {
            date_column: get_date_range(
                connection,
                table_name,
                date_column,
            )
            for date_column
            in date_columns
        }

        category_breakdowns: list[
            CategoryBreakdown
        ] = []

        if primary_measure:
            for category in category_columns:
                category_breakdowns.append(
                    get_top_category_values(
                        connection,
                        table_name,
                        category,
                        primary_measure,
                    )
                )

        quick_summary = build_quick_summary(
            total_rows=total_rows,
            primary_measure=primary_measure,
            measures=measures,
            category_breakdowns=category_breakdowns,
            date_ranges=date_ranges,
        )

        suggested_questions = build_suggested_questions(
            primary_measure,
            category_columns,
            measure_columns,
        )

        profile = BusinessProfile(
            dataset_name=clean_dataset,
            analytics_table=(
                f"analytics.{table_name}"
            ),
            total_rows=total_rows,
            date_ranges=date_ranges,
            measures=measures,
            category_breakdowns=(
                category_breakdowns
            ),
            primary_measure=(
                primary_measure
            ),
            quick_summary=(
                quick_summary
            ),
            suggested_questions=(
                suggested_questions
            ),
            generated_at=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        )

        save_profile(
            connection,
            profile,
        )

        connection.commit()

        return profile


def profile_to_dict(
    profile: BusinessProfile,
) -> dict[str, Any]:
    return {
        "dataset_name": profile.dataset_name,
        "analytics_table": (
            profile.analytics_table
        ),
        "total_rows": profile.total_rows,
        "date_ranges": profile.date_ranges,
        "measures": [
            asdict(
                measure
            )
            for measure
            in profile.measures
        ],
        "category_breakdowns": [
            asdict(
                breakdown
            )
            for breakdown
            in profile.category_breakdowns
        ],
        "primary_measure": (
            profile.primary_measure
        ),
        "quick_summary": (
            profile.quick_summary
        ),
        "suggested_questions": (
            profile.suggested_questions
        ),
        "generated_at": (
            profile.generated_at
        ),
    }

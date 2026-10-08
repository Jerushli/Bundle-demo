from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from psycopg import sql

from backend.dataset_analytics import (
    DatasetSchema,
    get_active_dataset_schema,
)
from backend.dataset_security import (
    enforce_column_access,
    enforce_dataset_access,
    enforce_operation_access,
    get_dataset_permission,
)
from backend.ingestion import (
    get_ingest_connection,
)


MAX_ABS_CHANGE_PERCENT = 500.0


@dataclass(frozen=True)
class ScenarioAssumption:
    kind: str
    measure: str
    change_percent: float
    group_by: str | None
    group_value: str | None
    description: str


@dataclass(frozen=True)
class ScenarioResult:
    dataset_name: str
    scenario_type: str
    measure: str
    group_by: str | None
    group_value: str | None
    baseline_value: float
    change_percent: float
    projected_value: float
    absolute_change: float
    direction: str
    assumption: ScenarioAssumption
    limitations: list[str]


def _split_table(
    analytics_table: str,
) -> tuple[str, str]:
    if "." in analytics_table:
        return tuple(
            analytics_table.split(
                ".",
                1,
            )
        )

    return (
        "analytics",
        analytics_table,
    )


def _allowed_dimension(
    *,
    schema: DatasetSchema,
    column: str,
) -> bool:
    return (
        column in schema.categories
    )


def _baseline_sum(
    *,
    schema: DatasetSchema,
    measure: str,
    group_by: str | None,
    group_value: str | None,
) -> float:
    schema_name, table_name = _split_table(
        schema.analytics_table
    )

    if group_by is None:
        query = sql.SQL(
            """
            SELECT
                COALESCE(
                    SUM({measure}),
                    0
                )::double precision
            FROM {schema_name}.{table_name}
            WHERE {measure} IS NOT NULL
            """
        ).format(
            measure=sql.Identifier(
                measure
            ),
            schema_name=sql.Identifier(
                schema_name
            ),
            table_name=sql.Identifier(
                table_name
            ),
        )

        params: tuple[Any, ...] = ()

    else:
        query = sql.SQL(
            """
            SELECT
                COALESCE(
                    SUM({measure}),
                    0
                )::double precision
            FROM {schema_name}.{table_name}
            WHERE
                {measure} IS NOT NULL
                AND CAST(
                    {group_by}
                    AS TEXT
                ) = %s
            """
        ).format(
            measure=sql.Identifier(
                measure
            ),
            schema_name=sql.Identifier(
                schema_name
            ),
            table_name=sql.Identifier(
                table_name
            ),
            group_by=sql.Identifier(
                group_by
            ),
        )

        params = (
            str(
                group_value
            ),
        )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                query,
                params,
            )

            value = cur.fetchone()[0]

    return float(
        value
        or 0.0
    )


def get_scenario_capabilities(
    *,
    role: str,
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

    return {
        "dataset_name": schema.dataset_name,
        "scenario_types": [
            "measure_percent_change",
        ],
        "measures": list(
            schema.measures
        ),
        "dimensions": sorted(
            set(
                schema.categories
            )
        ),
        "max_absolute_change_percent": (
            MAX_ABS_CHANGE_PERCENT
        ),
        "important_limitation": (
            "The engine calculates outcomes from explicit assumptions. "
            "It does not infer causal effects such as investment ROI, "
            "price elasticity, or demand response without a validated model."
        ),
    }


def simulate_measure_percent_change(
    *,
    role: str,
    measure: str,
    change_percent: float,
    group_by: str | None = None,
    group_value: str | None = None,
) -> ScenarioResult:
    change = float(
        change_percent
    )

    if abs(
        change
    ) > MAX_ABS_CHANGE_PERCENT:
        raise ValueError(
            "Scenario change is outside the supported safety range "
            f"of ±{MAX_ABS_CHANGE_PERCENT:g}%."
        )

    if (
        group_by is None
        and group_value is not None
    ) or (
        group_by is not None
        and group_value is None
    ):
        raise ValueError(
            "group_by and group_value must be supplied together."
        )

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
        operation="aggregate",
    )

    if measure not in schema.measures:
        raise ValueError(
            f"Measure {measure!r} is not available or permitted. "
            f"Allowed measures: {', '.join(schema.measures)}"
        )

    enforce_column_access(
        permission=permission,
        column=measure,
    )

    if group_by is not None:
        if not _allowed_dimension(
            schema=schema,
            column=group_by,
        ):
            raise ValueError(
                f"Dimension {group_by!r} is not available or permitted."
            )

        enforce_column_access(
            permission=permission,
            column=group_by,
        )

    baseline = _baseline_sum(
        schema=schema,
        measure=measure,
        group_by=group_by,
        group_value=group_value,
    )

    if (
        group_by is not None
        and baseline == 0
    ):
        raise ValueError(
            f"No non-zero {measure!r} baseline was found for "
            f"{group_by}={group_value!r}."
        )

    projected = (
        baseline
        * (
            1.0
            + change
            / 100.0
        )
    )

    absolute_change = (
        projected
        - baseline
    )

    if change > 0:
        direction = "increase"
    elif change < 0:
        direction = "decrease"
    else:
        direction = "no_change"

    scope = (
        f" for {group_by}={group_value}"
        if group_by is not None
        else ""
    )

    assumption = ScenarioAssumption(
        kind="explicit_measure_percent_change",
        measure=measure,
        change_percent=change,
        group_by=group_by,
        group_value=group_value,
        description=(
            f"Assume {measure}{scope} changes by {change:+.2f}% "
            "while all other factors are held constant."
        ),
    )

    limitations = [
        (
            "This is a deterministic what-if calculation, not a forecast "
            "or causal prediction."
        ),
        (
            "The calculation assumes the requested percentage change occurs "
            "exactly and holds other business factors constant."
        ),
        (
            "It does not estimate demand response, price elasticity, "
            "investment ROI, competitor behavior, macroeconomic changes, "
            "or operational constraints."
        ),
    ]

    return ScenarioResult(
        dataset_name=schema.dataset_name,
        scenario_type=(
            "measure_percent_change"
        ),
        measure=measure,
        group_by=group_by,
        group_value=group_value,
        baseline_value=round(
            baseline,
            2,
        ),
        change_percent=round(
            change,
            4,
        ),
        projected_value=round(
            projected,
            2,
        ),
        absolute_change=round(
            absolute_change,
            2,
        ),
        direction=direction,
        assumption=assumption,
        limitations=limitations,
    )


def scenario_to_dict(
    result: ScenarioResult,
) -> dict[str, Any]:
    return asdict(
        result
    )

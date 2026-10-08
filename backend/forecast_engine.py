from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt
from statistics import mean
from typing import Any

from psycopg import sql

from backend.dataset_analytics import (
    DatasetSchema,
    get_active_dataset_schema,
)
from backend.dataset_profiles import (
    get_latest_business_profile,
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


MIN_HISTORY_POINTS = 6
DEFAULT_LOOKBACK_MONTHS = 24
MAX_LOOKBACK_MONTHS = 60
MAX_FORECAST_MONTHS = 12
Z_95 = 1.96


@dataclass(frozen=True)
class ForecastPoint:
    period: str
    forecast: float
    lower_95: float
    upper_95: float


@dataclass(frozen=True)
class HistoricalPoint:
    period: str
    value: float


@dataclass(frozen=True)
class ForecastDiagnostics:
    method: str
    observations: int
    lookback_months: int
    slope_per_month: float
    intercept: float
    r_squared: float | None
    residual_std: float
    backtest_points: int
    backtest_mae: float | None
    backtest_mape_percent: float | None
    confidence: str
    warnings: list[str]


@dataclass(frozen=True)
class ForecastResult:
    dataset_name: str
    measure: str
    date_column: str
    aggregation: str
    group_by: str | None
    group_value: str | None
    scope: str
    horizon_months: int
    history_start: str
    history_end: str
    historical: list[HistoricalPoint]
    forecast: list[ForecastPoint]
    diagnostics: ForecastDiagnostics


def _split_table(
    analytics_table: str,
) -> tuple[str, str]:
    if "." in analytics_table:
        schema_name, table_name = analytics_table.split(
            ".",
            1,
        )
    else:
        schema_name = "analytics"
        table_name = analytics_table

    return (
        schema_name,
        table_name,
    )


def _month_number(
    value: date,
) -> int:
    return (
        value.year * 12
        + value.month
    )


def _add_months(
    value: date,
    months: int,
) -> date:
    number = (
        value.year * 12
        + (value.month - 1)
        + months
    )

    year = number // 12
    month = (
        number % 12
    ) + 1

    return date(
        year,
        month,
        1,
    )


def _linear_fit(
    xs: list[float],
    ys: list[float],
) -> tuple[
    float,
    float,
    float | None,
    float,
]:
    if len(xs) != len(ys):
        raise ValueError(
            "Forecast x/y history lengths differ."
        )

    if len(xs) < 2:
        raise ValueError(
            "At least two observations are required."
        )

    x_bar = mean(xs)
    y_bar = mean(ys)

    sxx = sum(
        (x - x_bar) ** 2
        for x in xs
    )

    if sxx == 0:
        raise ValueError(
            "Historical periods do not span enough time."
        )

    slope = (
        sum(
            (x - x_bar)
            * (y - y_bar)
            for x, y
            in zip(
                xs,
                ys,
            )
        )
        / sxx
    )

    intercept = (
        y_bar
        - slope
        * x_bar
    )

    predictions = [
        intercept
        + slope * x
        for x in xs
    ]

    residuals = [
        actual - predicted
        for actual, predicted
        in zip(
            ys,
            predictions,
        )
    ]

    sse = sum(
        residual ** 2
        for residual
        in residuals
    )

    sst = sum(
        (actual - y_bar) ** 2
        for actual in ys
    )

    r_squared = (
        1.0 - sse / sst
        if sst > 0
        else None
    )

    degrees = max(
        1,
        len(xs) - 2,
    )

    residual_std = sqrt(
        sse / degrees
    )

    return (
        slope,
        intercept,
        r_squared,
        residual_std,
    )


def _backtest(
    xs: list[float],
    ys: list[float],
) -> tuple[
    int,
    float | None,
    float | None,
]:
    if len(xs) < 8:
        return (
            0,
            None,
            None,
        )

    holdout = min(
        3,
        max(
            1,
            len(xs) // 5,
        ),
    )

    train_x = xs[:-holdout]
    train_y = ys[:-holdout]
    test_x = xs[-holdout:]
    test_y = ys[-holdout:]

    slope, intercept, _, _ = (
        _linear_fit(
            train_x,
            train_y,
        )
    )

    predictions = [
        intercept
        + slope * x
        for x in test_x
    ]

    absolute_errors = [
        abs(
            actual - predicted
        )
        for actual, predicted
        in zip(
            test_y,
            predictions,
        )
    ]

    mae = mean(
        absolute_errors
    )

    percentage_errors = [
        abs(
            actual - predicted
        )
        / abs(
            actual
        )
        * 100
        for actual, predicted
        in zip(
            test_y,
            predictions,
        )
        if actual != 0
    ]

    mape = (
        mean(
            percentage_errors
        )
        if percentage_errors
        else None
    )

    return (
        holdout,
        mae,
        mape,
    )


def _confidence_label(
    *,
    observations: int,
    mape: float | None,
    r_squared: float | None,
) -> str:
    if observations < 12:
        return "low"

    if (
        mape is not None
        and mape <= 10
        and (
            r_squared is None
            or r_squared >= 0.50
        )
    ):
        return "high"

    if (
        mape is not None
        and mape <= 25
    ):
        return "medium"

    if (
        r_squared is not None
        and r_squared >= 0.60
    ):
        return "medium"

    return "low"


def _choose_measure(
    *,
    requested: str | None,
    schema: DatasetSchema,
) -> str:
    if requested:
        if requested not in schema.measures:
            raise ValueError(
                f"Measure {requested!r} is not available or permitted. "
                f"Allowed measures: {', '.join(schema.measures)}"
            )

        return requested

    try:
        profile = get_latest_business_profile(
            schema.dataset_name
        )

        primary = profile.get(
            "primary_measure"
        )

        if (
            isinstance(
                primary,
                str,
            )
            and primary
            in schema.measures
        ):
            return primary

    except Exception:
        pass

    for preferred in (
        "profit",
        "sales",
        "revenue",
        "gross_sales",
    ):
        if preferred in schema.measures:
            return preferred

    if not schema.measures:
        raise ValueError(
            "The active dataset has no permitted numeric measure "
            "that can be forecast."
        )

    return schema.measures[0]


def _choose_date_column(
    *,
    requested: str | None,
    schema: DatasetSchema,
) -> str:
    if requested:
        if requested not in schema.dates:
            raise ValueError(
                f"Date column {requested!r} is not available or permitted. "
                f"Allowed date columns: {', '.join(schema.dates)}"
            )

        return requested

    if not schema.dates:
        raise ValueError(
            "The active dataset has no permitted date column."
        )

    return schema.dates[0]


def _load_monthly_history(
    *,
    schema: DatasetSchema,
    measure: str,
    date_column: str,
    lookback_months: int,
    group_by: str | None = None,
    group_value: str | None = None,
) -> list[
    tuple[
        date,
        float,
    ]
]:
    schema_name, table_name = _split_table(
        schema.analytics_table
    )

    if group_by is None:
        query = sql.SQL(
            """
            WITH monthly AS (
                SELECT
                    date_trunc(
                        'month',
                        {date_column}
                    )::date AS month_start,
                    SUM(
                        {measure}
                    )::double precision AS value
                FROM {schema_name}.{table_name}
                WHERE
                    {date_column} IS NOT NULL
                    AND {measure} IS NOT NULL
                GROUP BY 1
            )
            SELECT
                month_start,
                value
            FROM monthly
            ORDER BY month_start DESC
            LIMIT %s
            """
        ).format(
            date_column=sql.Identifier(
                date_column
            ),
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

        params = (
            lookback_months,
        )

    else:
        query = sql.SQL(
            """
            WITH monthly AS (
                SELECT
                    date_trunc(
                        'month',
                        {date_column}
                    )::date AS month_start,
                    SUM(
                        {measure}
                    )::double precision AS value
                FROM {schema_name}.{table_name}
                WHERE
                    {date_column} IS NOT NULL
                    AND {measure} IS NOT NULL
                    AND CAST(
                        {group_by}
                        AS TEXT
                    ) = %s
                GROUP BY 1
            )
            SELECT
                month_start,
                value
            FROM monthly
            ORDER BY month_start DESC
            LIMIT %s
            """
        ).format(
            date_column=sql.Identifier(
                date_column
            ),
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
            lookback_months,
        )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                query,
                params,
            )

            rows = cur.fetchall()

    history = [
        (
            row[0],
            float(
                row[1]
            ),
        )
        for row in reversed(
            rows
        )
    ]

    return history


def get_forecast_capabilities(
    *,
    role: str,
) -> dict[str, Any]:
    schema = get_active_dataset_schema(
        role=role
    )

    permission = get_dataset_permission(
        dataset_name=(
            schema.dataset_name
        ),
        role=role,
    )

    enforce_dataset_access(
        permission=permission
    )

    if (
        "trend"
        not in permission.allowed_operations
    ):
        return {
            "dataset_name": (
                schema.dataset_name
            ),
            "forecasting_allowed": False,
            "measures": [],
            "date_columns": [],
            "reason": (
                "The current role does not have trend access."
            ),
        }

    return {
        "dataset_name": (
            schema.dataset_name
        ),
        "forecasting_allowed": True,
        "measures": list(
            schema.measures
        ),
        "date_columns": list(
            schema.dates
        ),
        "max_horizon_months": (
            MAX_FORECAST_MONTHS
        ),
        "max_lookback_months": (
            MAX_LOOKBACK_MONTHS
        ),
        "minimum_history_points": (
            MIN_HISTORY_POINTS
        ),
    }


def forecast_monthly_measure(
    *,
    role: str,
    measure: str | None = None,
    date_column: str | None = None,
    horizon_months: int = 3,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    group_by: str | None = None,
    group_value: str | None = None,
) -> ForecastResult:
    horizon = max(
        1,
        min(
            int(
                horizon_months
            ),
            MAX_FORECAST_MONTHS,
        ),
    )

    lookback = max(
        MIN_HISTORY_POINTS,
        min(
            int(
                lookback_months
            ),
            MAX_LOOKBACK_MONTHS,
        ),
    )

    schema = get_active_dataset_schema(
        role=role
    )

    permission = get_dataset_permission(
        dataset_name=(
            schema.dataset_name
        ),
        role=role,
    )

    enforce_dataset_access(
        permission=permission
    )

    enforce_operation_access(
        permission=permission,
        operation="trend",
    )

    selected_measure = _choose_measure(
        requested=measure,
        schema=schema,
    )

    selected_date = _choose_date_column(
        requested=date_column,
        schema=schema,
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

    if group_by is not None:
        if group_by not in schema.categories:
            raise ValueError(
                f"Forecast target dimension {group_by!r} is not "
                "available or permitted."
            )

        enforce_column_access(
            permission=permission,
            column=group_by,
        )

    enforce_column_access(
        permission=permission,
        column=selected_measure,
    )

    enforce_column_access(
        permission=permission,
        column=selected_date,
    )

    history = _load_monthly_history(
        schema=schema,
        measure=selected_measure,
        date_column=selected_date,
        lookback_months=lookback,
        group_by=group_by,
        group_value=group_value,
    )

    if len(history) < MIN_HISTORY_POINTS:
        scope_text = (
            f" for {group_by}={group_value!r}"
            if group_by is not None
            else ""
        )

        raise ValueError(
            "Not enough monthly history to forecast safely"
            f"{scope_text}. "
            f"Need at least {MIN_HISTORY_POINTS} observed months; "
            f"found {len(history)}."
        )

    first_month = history[0][0]

    xs = [
        float(
            _month_number(
                period
            )
            - _month_number(
                first_month
            )
        )
        for period, _
        in history
    ]

    ys = [
        value
        for _, value
        in history
    ]

    (
        slope,
        intercept,
        r_squared,
        residual_std,
    ) = _linear_fit(
        xs,
        ys,
    )

    (
        backtest_points,
        backtest_mae,
        backtest_mape,
    ) = _backtest(
        xs,
        ys,
    )

    x_bar = mean(
        xs
    )

    sxx = sum(
        (x - x_bar) ** 2
        for x in xs
    )

    last_month = history[-1][0]

    forecast_points: list[
        ForecastPoint
    ] = []

    for step in range(
        1,
        horizon + 1,
    ):
        future_period = _add_months(
            last_month,
            step,
        )

        future_x = float(
            _month_number(
                future_period
            )
            - _month_number(
                first_month
            )
        )

        estimate = (
            intercept
            + slope
            * future_x
        )

        prediction_std = (
            residual_std
            * sqrt(
                1.0
                + 1.0
                / len(
                    xs
                )
                + (
                    (future_x - x_bar) ** 2
                    / sxx
                    if sxx > 0
                    else 0.0
                )
            )
        )

        margin = (
            Z_95
            * prediction_std
        )

        forecast_points.append(
            ForecastPoint(
                period=(
                    future_period.isoformat()
                ),
                forecast=round(
                    estimate,
                    2,
                ),
                lower_95=round(
                    estimate - margin,
                    2,
                ),
                upper_95=round(
                    estimate + margin,
                    2,
                ),
            )
        )

    warnings: list[str] = []

    if len(history) < 12:
        warnings.append(
            "Less than 12 observed months are available; "
            "seasonal business behavior cannot be assessed reliably."
        )

    if len(history) < 24:
        warnings.append(
            "Less than 24 months of history are available; "
            "long-range forecasts should be treated cautiously."
        )

    if (
        r_squared is not None
        and r_squared < 0.25
    ):
        warnings.append(
            "Historical values have a weak linear trend fit."
        )

    if (
        backtest_mape is not None
        and backtest_mape > 25
    ):
        warnings.append(
            "Recent holdout error is high; forecast uncertainty is material."
        )

    if horizon > 6:
        warnings.append(
            "Forecast horizon exceeds six months; uncertainty grows "
            "as the projection moves further from observed data."
        )

    confidence = _confidence_label(
        observations=len(
            history
        ),
        mape=backtest_mape,
        r_squared=r_squared,
    )

    diagnostics = ForecastDiagnostics(
        method="monthly_linear_trend_v1",
        observations=len(
            history
        ),
        lookback_months=lookback,
        slope_per_month=round(
            slope,
            6,
        ),
        intercept=round(
            intercept,
            6,
        ),
        r_squared=(
            round(
                r_squared,
                6,
            )
            if r_squared
            is not None
            else None
        ),
        residual_std=round(
            residual_std,
            6,
        ),
        backtest_points=(
            backtest_points
        ),
        backtest_mae=(
            round(
                backtest_mae,
                2,
            )
            if backtest_mae
            is not None
            else None
        ),
        backtest_mape_percent=(
            round(
                backtest_mape,
                2,
            )
            if backtest_mape
            is not None
            else None
        ),
        confidence=confidence,
        warnings=warnings,
    )

    return ForecastResult(
        dataset_name=(
            schema.dataset_name
        ),
        measure=selected_measure,
        date_column=selected_date,
        aggregation="sum",
        group_by=group_by,
        group_value=group_value,
        scope=(
            "target_specific"
            if group_by is not None
            else "overall_dataset"
        ),
        horizon_months=horizon,
        history_start=(
            history[0][0]
            .isoformat()
        ),
        history_end=(
            history[-1][0]
            .isoformat()
        ),
        historical=[
            HistoricalPoint(
                period=period.isoformat(),
                value=round(
                    value,
                    2,
                ),
            )
            for period, value
            in history
        ],
        forecast=(
            forecast_points
        ),
        diagnostics=diagnostics,
    )


def forecast_to_dict(
    result: ForecastResult,
) -> dict[str, Any]:
    return asdict(
        result
    )

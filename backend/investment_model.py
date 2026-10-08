from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from psycopg import sql

from backend.dataset_analytics import (
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


MAX_INVESTMENT = 1_000_000_000_000.0
MAX_UPLIFT_PERCENT = 500.0
MAX_MARGIN_PERCENT = 100.0
MAX_HORIZON_MONTHS = 120
MAX_BASELINE_MONTHS = 120
MAX_HURDLE_PERCENT = 500.0
MAX_PAYBACK_MONTHS = 240


@dataclass(frozen=True)
class InvestmentAssumptions:
    investment_amount: float
    expected_revenue_uplift_percent: float
    contribution_margin_percent: float
    horizon_months: int
    baseline_period_months: int
    hurdle_rate_percent: float
    max_payback_months: float


@dataclass(frozen=True)
class InvestmentResult:
    dataset_name: str
    target_column: str
    target_value: str
    baseline_measure: str
    baseline_value: float
    baseline_period_months: int
    horizon_months: int
    baseline_value_for_horizon: float
    investment_amount: float
    expected_revenue_uplift_percent: float
    contribution_margin_percent: float
    incremental_revenue: float
    incremental_operating_profit: float
    net_benefit_after_investment: float
    roi_percent: float
    payback_months: float | None
    hurdle_rate_percent: float
    hurdle_rate_pass: bool
    max_payback_months: float
    payback_pass: bool | None
    rule_result: str
    assumptions: InvestmentAssumptions
    warnings: list[str]
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


def _validate_inputs(
    *,
    investment_amount: float,
    expected_revenue_uplift_percent: float,
    contribution_margin_percent: float,
    horizon_months: int,
    baseline_period_months: int,
    hurdle_rate_percent: float,
    max_payback_months: float,
):
    if investment_amount <= 0:
        raise ValueError(
            "investment_amount must be greater than zero."
        )

    if investment_amount > MAX_INVESTMENT:
        raise ValueError(
            "investment_amount exceeds the configured safety limit."
        )

    if (
        expected_revenue_uplift_percent
        < -100
        or expected_revenue_uplift_percent
        > MAX_UPLIFT_PERCENT
    ):
        raise ValueError(
            "expected_revenue_uplift_percent must be between "
            "-100 and 500."
        )

    if (
        contribution_margin_percent
        < 0
        or contribution_margin_percent
        > MAX_MARGIN_PERCENT
    ):
        raise ValueError(
            "contribution_margin_percent must be between 0 and 100."
        )

    if (
        horizon_months < 1
        or horizon_months
        > MAX_HORIZON_MONTHS
    ):
        raise ValueError(
            "horizon_months must be between 1 and 120."
        )

    if (
        baseline_period_months < 1
        or baseline_period_months
        > MAX_BASELINE_MONTHS
    ):
        raise ValueError(
            "baseline_period_months must be between 1 and 120."
        )

    if (
        hurdle_rate_percent < 0
        or hurdle_rate_percent
        > MAX_HURDLE_PERCENT
    ):
        raise ValueError(
            "hurdle_rate_percent must be between 0 and 500."
        )

    if (
        max_payback_months <= 0
        or max_payback_months
        > MAX_PAYBACK_MONTHS
    ):
        raise ValueError(
            "max_payback_months must be greater than 0 and no more than 240."
        )


def _target_baseline(
    *,
    role: str,
    measure: str,
    target_column: str,
    target_value: str,
) -> tuple[
    str,
    float,
]:
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
        operation="aggregate",
    )

    if measure not in schema.measures:
        raise ValueError(
            f"Baseline measure {measure!r} is not available or permitted. "
            f"Allowed measures: {', '.join(schema.measures)}"
        )

    if target_column not in schema.categories:
        raise ValueError(
            f"Target column {target_column!r} is not available or permitted."
        )

    enforce_column_access(
        permission=permission,
        column=measure,
    )

    enforce_column_access(
        permission=permission,
        column=target_column,
    )

    schema_name, table_name = _split_table(
        schema.analytics_table
    )

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
                {target_column}
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
        target_column=sql.Identifier(
            target_column
        ),
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                query,
                (
                    str(
                        target_value
                    ),
                ),
            )

            value = float(
                cur.fetchone()[0]
                or 0.0
            )

    if value <= 0:
        raise ValueError(
            f"No positive {measure!r} baseline was found for "
            f"{target_column}={target_value!r}."
        )

    return (
        schema.dataset_name,
        value,
    )


def calculate_investment_scenario(
    *,
    role: str,
    target_column: str,
    target_value: str,
    investment_amount: float,
    expected_revenue_uplift_percent: float,
    contribution_margin_percent: float,
    horizon_months: int,
    baseline_period_months: int,
    hurdle_rate_percent: float,
    max_payback_months: float,
    baseline_measure: str = "sales",
) -> InvestmentResult:
    _validate_inputs(
        investment_amount=float(
            investment_amount
        ),
        expected_revenue_uplift_percent=float(
            expected_revenue_uplift_percent
        ),
        contribution_margin_percent=float(
            contribution_margin_percent
        ),
        horizon_months=int(
            horizon_months
        ),
        baseline_period_months=int(
            baseline_period_months
        ),
        hurdle_rate_percent=float(
            hurdle_rate_percent
        ),
        max_payback_months=float(
            max_payback_months
        ),
    )

    dataset_name, baseline_value = _target_baseline(
        role=role,
        measure=baseline_measure,
        target_column=target_column,
        target_value=target_value,
    )

    horizon_factor = (
        float(
            horizon_months
        )
        / float(
            baseline_period_months
        )
    )

    baseline_for_horizon = (
        baseline_value
        * horizon_factor
    )

    incremental_revenue = (
        baseline_for_horizon
        * (
            float(
                expected_revenue_uplift_percent
            )
            / 100.0
        )
    )

    incremental_profit = (
        incremental_revenue
        * (
            float(
                contribution_margin_percent
            )
            / 100.0
        )
    )

    net_benefit = (
        incremental_profit
        - float(
            investment_amount
        )
    )

    roi_percent = (
        net_benefit
        / float(
            investment_amount
        )
        * 100.0
    )

    monthly_incremental_profit = (
        incremental_profit
        / float(
            horizon_months
        )
    )

    if monthly_incremental_profit > 0:
        payback_months = (
            float(
                investment_amount
            )
            / monthly_incremental_profit
        )
    else:
        payback_months = None

    hurdle_pass = (
        roi_percent
        >= float(
            hurdle_rate_percent
        )
    )

    payback_pass = (
        payback_months
        <= float(
            max_payback_months
        )
        if payback_months
        is not None
        else None
    )

    if (
        hurdle_pass
        and payback_pass is True
    ):
        rule_result = "passes_rules"

    elif (
        not hurdle_pass
        and payback_pass is False
    ):
        rule_result = "fails_rules"

    else:
        rule_result = "mixed"

    assumptions = InvestmentAssumptions(
        investment_amount=round(
            float(
                investment_amount
            ),
            2,
        ),
        expected_revenue_uplift_percent=round(
            float(
                expected_revenue_uplift_percent
            ),
            4,
        ),
        contribution_margin_percent=round(
            float(
                contribution_margin_percent
            ),
            4,
        ),
        horizon_months=int(
            horizon_months
        ),
        baseline_period_months=int(
            baseline_period_months
        ),
        hurdle_rate_percent=round(
            float(
                hurdle_rate_percent
            ),
            4,
        ),
        max_payback_months=round(
            float(
                max_payback_months
            ),
            2,
        ),
    )

    warnings: list[str] = []

    if expected_revenue_uplift_percent < 0:
        warnings.append(
            "The supplied revenue-uplift assumption is negative."
        )

    if horizon_months != baseline_period_months:
        warnings.append(
            "The observed baseline is scaled linearly to the scenario horizon."
        )

    if payback_months is None:
        warnings.append(
            "Payback cannot be achieved because the calculated incremental "
            "operating profit is not positive."
        )

    if expected_revenue_uplift_percent >= 50:
        warnings.append(
            "The supplied revenue-uplift assumption is large and should be "
            "supported by strong external evidence or a validated response model."
        )

    limitations = [
        (
            "This is a deterministic investment scenario based on explicit "
            "assumptions; it is not a causal prediction."
        ),
        (
            "The expected revenue uplift is supplied by the user/company and "
            "is not inferred by the LLM."
        ),
        (
            "The contribution margin applies only to incremental revenue in "
            "this model."
        ),
        (
            "Baseline scaling assumes business activity is proportional across "
            "the supplied time periods."
        ),
        (
            "This foundation does not yet model tax, financing cost, working "
            "capital, depreciation, terminal value, NPV, or IRR."
        ),
        (
            "Passing the configured rules does not automatically authorize "
            "the investment; management approval remains required."
        ),
    ]

    return InvestmentResult(
        dataset_name=dataset_name,
        target_column=target_column,
        target_value=target_value,
        baseline_measure=baseline_measure,
        baseline_value=round(
            baseline_value,
            2,
        ),
        baseline_period_months=int(
            baseline_period_months
        ),
        horizon_months=int(
            horizon_months
        ),
        baseline_value_for_horizon=round(
            baseline_for_horizon,
            2,
        ),
        investment_amount=round(
            float(
                investment_amount
            ),
            2,
        ),
        expected_revenue_uplift_percent=round(
            float(
                expected_revenue_uplift_percent
            ),
            4,
        ),
        contribution_margin_percent=round(
            float(
                contribution_margin_percent
            ),
            4,
        ),
        incremental_revenue=round(
            incremental_revenue,
            2,
        ),
        incremental_operating_profit=round(
            incremental_profit,
            2,
        ),
        net_benefit_after_investment=round(
            net_benefit,
            2,
        ),
        roi_percent=round(
            roi_percent,
            2,
        ),
        payback_months=(
            round(
                payback_months,
                2,
            )
            if payback_months
            is not None
            else None
        ),
        hurdle_rate_percent=round(
            float(
                hurdle_rate_percent
            ),
            4,
        ),
        hurdle_rate_pass=(
            hurdle_pass
        ),
        max_payback_months=round(
            float(
                max_payback_months
            ),
            2,
        ),
        payback_pass=(
            payback_pass
        ),
        rule_result=rule_result,
        assumptions=assumptions,
        warnings=warnings,
        limitations=limitations,
    )


def investment_result_to_dict(
    result: InvestmentResult,
) -> dict[str, Any]:
    return asdict(
        result
    )

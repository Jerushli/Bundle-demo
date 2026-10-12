from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


PeriodUnit = Literal[
    "monthly",
    "yearly",
]

MAX_SCENARIOS = 12
MAX_PERIODS = 600
MAX_ABSOLUTE_CASH_FLOW = 1_000_000_000_000.0
MAX_DISCOUNT_RATE_PERCENT = 500.0


@dataclass(frozen=True)
class VariableCashFlowRow:
    period: int
    period_label: str
    base_cash_flow: float
    working_capital_recovery: float
    terminal_value: float
    total_cash_flow: float
    discount_factor: float
    discounted_cash_flow: float
    cumulative_cash_flow: float
    cumulative_discounted_cash_flow: float


@dataclass(frozen=True)
class ScenarioFinanceResult:
    name: str
    period_unit: PeriodUnit
    annual_discount_rate_percent: float
    periodic_discount_rate_percent: float
    initial_investment: float
    working_capital_outflow: float
    total_initial_outflow: float
    cash_flows_input: list[float]
    working_capital_recovery: float
    terminal_value: float
    total_undiscounted_future_cash_flow: float
    present_value_future_cash_flows: float
    npv: float
    profitability_index: float | None
    simple_return_multiple: float | None
    simple_roi_percent: float | None
    irr_periodic_percent: float | None
    irr_annualized_percent: float | None
    irr_status: str
    irr_note: str
    simple_payback_periods: int | None
    discounted_payback_periods: int | None
    schedule: list[VariableCashFlowRow]
    limitations: list[str]


@dataclass(frozen=True)
class ScenarioComparisonResult:
    ranking_method: str
    scenario_count: int
    period_unit: PeriodUnit
    annual_discount_rate_percent: float
    ranking: list[dict[str, Any]]
    scenarios: list[ScenarioFinanceResult]
    comparison_notes: list[str]


def _periodic_rate(
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit,
) -> float:
    annual = float(
        annual_discount_rate_percent
    ) / 100.0

    if period_unit == "yearly":
        return annual

    return (
        (1.0 + annual)
        ** (1.0 / 12.0)
        - 1.0
    )


def _sign_changes(
    values: list[float],
) -> int:
    non_zero = [
        value
        for value in values
        if abs(value) > 1e-12
    ]

    if len(non_zero) < 2:
        return 0

    changes = 0
    previous_positive = non_zero[0] > 0

    for value in non_zero[1:]:
        current_positive = value > 0

        if current_positive != previous_positive:
            changes += 1

        previous_positive = current_positive

    return changes


def _npv_at_rate(
    cash_flows: list[float],
    rate: float,
) -> float:
    if rate <= -1.0:
        raise ValueError(
            "IRR rate must be greater than -100%."
        )

    return sum(
        cash_flow
        / (
            (1.0 + rate)
            ** period
        )
        for period, cash_flow
        in enumerate(cash_flows)
    )


def _solve_irr(
    cash_flows: list[float],
) -> tuple[
    float | None,
    str,
    str,
]:
    changes = _sign_changes(
        cash_flows
    )

    if changes == 0:
        return (
            None,
            "not_available",
            (
                "IRR is unavailable because the supplied schedule does not "
                "contain both negative and positive cash flows."
            ),
        )

    if changes > 1:
        return (
            None,
            "ambiguous",
            (
                "IRR is not reported because the complete cash-flow series "
                "changes sign more than once and may have multiple IRRs."
            ),
        )

    lower = -0.999999
    upper = 1.0

    f_lower = _npv_at_rate(
        cash_flows,
        lower,
    )

    f_upper = _npv_at_rate(
        cash_flows,
        upper,
    )

    safety_upper = 1_000_000.0

    while (
        f_lower * f_upper > 0
        and upper < safety_upper
    ):
        upper *= 2.0

        f_upper = _npv_at_rate(
            cash_flows,
            upper,
        )

    if f_lower * f_upper > 0:
        return (
            None,
            "not_bracketed",
            (
                "IRR could not be bracketed within the configured "
                "numerical search range."
            ),
        )

    for _ in range(250):
        midpoint = (
            lower + upper
        ) / 2.0

        f_mid = _npv_at_rate(
            cash_flows,
            midpoint,
        )

        if abs(f_mid) < 1e-8:
            return (
                midpoint,
                "available",
                (
                    "IRR was solved numerically from the explicitly "
                    "supplied variable cash-flow schedule."
                ),
            )

        if f_lower * f_mid <= 0:
            upper = midpoint
            f_upper = f_mid

        else:
            lower = midpoint
            f_lower = f_mid

    return (
        (lower + upper) / 2.0,
        "available",
        (
            "IRR was solved numerically using deterministic bisection."
        ),
    )


def _validate_scenario(
    *,
    name: str,
    initial_investment: float,
    cash_flows: list[float],
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit,
    working_capital_outflow: float,
    working_capital_recovery: float,
    terminal_value: float,
):
    if not name.strip():
        raise ValueError(
            "Scenario name cannot be empty."
        )

    if initial_investment <= 0:
        raise ValueError(
            f"{name}: initial_investment must be greater than zero."
        )

    if not cash_flows:
        raise ValueError(
            f"{name}: cash_flows cannot be empty."
        )

    if len(cash_flows) > MAX_PERIODS:
        raise ValueError(
            f"{name}: cash_flows cannot exceed {MAX_PERIODS} periods."
        )

    if period_unit not in {
        "monthly",
        "yearly",
    }:
        raise ValueError(
            "period_unit must be 'monthly' or 'yearly'."
        )

    if (
        annual_discount_rate_percent < 0
        or annual_discount_rate_percent
        > MAX_DISCOUNT_RATE_PERCENT
    ):
        raise ValueError(
            "annual_discount_rate_percent must be between 0 and 500."
        )

    if working_capital_outflow < 0:
        raise ValueError(
            f"{name}: working_capital_outflow cannot be negative."
        )

    if working_capital_recovery < 0:
        raise ValueError(
            f"{name}: working_capital_recovery cannot be negative."
        )

    if terminal_value < 0:
        raise ValueError(
            f"{name}: terminal_value cannot be negative."
        )

    values = [
        initial_investment,
        working_capital_outflow,
        working_capital_recovery,
        terminal_value,
        *cash_flows,
    ]

    if any(
        abs(float(value))
        > MAX_ABSOLUTE_CASH_FLOW
        for value in values
    ):
        raise ValueError(
            f"{name}: one or more values exceed the configured safety limit."
        )


def calculate_variable_cash_flow_scenario(
    *,
    name: str,
    initial_investment: float,
    cash_flows: list[float],
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit = "yearly",
    working_capital_outflow: float = 0.0,
    working_capital_recovery: float = 0.0,
    terminal_value: float = 0.0,
) -> ScenarioFinanceResult:
    _validate_scenario(
        name=name,
        initial_investment=float(
            initial_investment
        ),
        cash_flows=[
            float(value)
            for value in cash_flows
        ],
        annual_discount_rate_percent=float(
            annual_discount_rate_percent
        ),
        period_unit=period_unit,
        working_capital_outflow=float(
            working_capital_outflow
        ),
        working_capital_recovery=float(
            working_capital_recovery
        ),
        terminal_value=float(
            terminal_value
        ),
    )

    rate = _periodic_rate(
        annual_discount_rate_percent=float(
            annual_discount_rate_percent
        ),
        period_unit=period_unit,
    )

    initial_investment = float(
        initial_investment
    )

    working_capital_outflow = float(
        working_capital_outflow
    )

    working_capital_recovery = float(
        working_capital_recovery
    )

    terminal_value = float(
        terminal_value
    )

    base_flows = [
        float(value)
        for value in cash_flows
    ]

    total_initial_outflow = (
        initial_investment
        + working_capital_outflow
    )

    cumulative = (
        -total_initial_outflow
    )

    cumulative_discounted = (
        -total_initial_outflow
    )

    total_future = 0.0
    pv_future = 0.0

    simple_payback: int | None = None
    discounted_payback: int | None = None

    schedule: list[
        VariableCashFlowRow
    ] = []

    full_series = [
        -total_initial_outflow
    ]

    for period, base_cash_flow in enumerate(
        base_flows,
        start=1,
    ):
        final_period = (
            period == len(
                base_flows
            )
        )

        wc_recovery = (
            working_capital_recovery
            if final_period
            else 0.0
        )

        period_terminal = (
            terminal_value
            if final_period
            else 0.0
        )

        total_cash_flow = (
            base_cash_flow
            + wc_recovery
            + period_terminal
        )

        discount_factor = (
            1.0
            / (
                (1.0 + rate)
                ** period
            )
        )

        discounted = (
            total_cash_flow
            * discount_factor
        )

        cumulative += (
            total_cash_flow
        )

        cumulative_discounted += (
            discounted
        )

        total_future += (
            total_cash_flow
        )

        pv_future += (
            discounted
        )

        full_series.append(
            total_cash_flow
        )

        if (
            simple_payback is None
            and cumulative >= 0
        ):
            simple_payback = period

        if (
            discounted_payback is None
            and cumulative_discounted >= 0
        ):
            discounted_payback = period

        schedule.append(
            VariableCashFlowRow(
                period=period,
                period_label=(
                    f"Month {period}"
                    if period_unit == "monthly"
                    else f"Year {period}"
                ),
                base_cash_flow=round(
                    base_cash_flow,
                    2,
                ),
                working_capital_recovery=round(
                    wc_recovery,
                    2,
                ),
                terminal_value=round(
                    period_terminal,
                    2,
                ),
                total_cash_flow=round(
                    total_cash_flow,
                    2,
                ),
                discount_factor=round(
                    discount_factor,
                    8,
                ),
                discounted_cash_flow=round(
                    discounted,
                    2,
                ),
                cumulative_cash_flow=round(
                    cumulative,
                    2,
                ),
                cumulative_discounted_cash_flow=round(
                    cumulative_discounted,
                    2,
                ),
            )
        )

    npv = (
        pv_future
        - total_initial_outflow
    )

    profitability_index = (
        pv_future
        / total_initial_outflow
        if total_initial_outflow > 0
        else None
    )

    simple_return_multiple = (
        total_future
        / total_initial_outflow
        if total_initial_outflow > 0
        else None
    )

    simple_roi_percent = (
        (
            total_future
            - total_initial_outflow
        )
        / total_initial_outflow
        * 100.0
        if total_initial_outflow > 0
        else None
    )

    irr_periodic, irr_status, irr_note = (
        _solve_irr(
            full_series
        )
    )

    irr_periodic_percent: float | None = None
    irr_annualized_percent: float | None = None

    if irr_periodic is not None:
        irr_periodic_percent = (
            irr_periodic
            * 100.0
        )

        if period_unit == "monthly":
            irr_annualized_percent = (
                (
                    (1.0 + irr_periodic)
                    ** 12.0
                    - 1.0
                )
                * 100.0
            )

        else:
            irr_annualized_percent = (
                irr_periodic_percent
            )

    limitations = [
        (
            "All future cash flows are explicit scenario assumptions, not "
            "predictions produced by Bundle."
        ),
        (
            "The comparison does not estimate probabilities for conservative, "
            "base, or optimistic scenarios."
        ),
        (
            "IRR is suppressed when the complete cash-flow series has multiple "
            "sign changes."
        ),
        (
            "Tax, financing structure, inflation, depreciation, and currency "
            "effects are included only if already reflected in the supplied "
            "cash flows."
        ),
        (
            "A higher NPV under one supplied scenario does not prove that its "
            "assumptions are more likely to occur."
        ),
    ]

    return ScenarioFinanceResult(
        name=name.strip(),
        period_unit=period_unit,
        annual_discount_rate_percent=round(
            float(
                annual_discount_rate_percent
            ),
            6,
        ),
        periodic_discount_rate_percent=round(
            rate * 100.0,
            8,
        ),
        initial_investment=round(
            initial_investment,
            2,
        ),
        working_capital_outflow=round(
            working_capital_outflow,
            2,
        ),
        total_initial_outflow=round(
            total_initial_outflow,
            2,
        ),
        cash_flows_input=[
            round(
                value,
                2,
            )
            for value in base_flows
        ],
        working_capital_recovery=round(
            working_capital_recovery,
            2,
        ),
        terminal_value=round(
            terminal_value,
            2,
        ),
        total_undiscounted_future_cash_flow=round(
            total_future,
            2,
        ),
        present_value_future_cash_flows=round(
            pv_future,
            2,
        ),
        npv=round(
            npv,
            2,
        ),
        profitability_index=(
            round(
                profitability_index,
                6,
            )
            if profitability_index
            is not None
            else None
        ),
        simple_return_multiple=(
            round(
                simple_return_multiple,
                6,
            )
            if simple_return_multiple
            is not None
            else None
        ),
        simple_roi_percent=(
            round(
                simple_roi_percent,
                4,
            )
            if simple_roi_percent
            is not None
            else None
        ),
        irr_periodic_percent=(
            round(
                irr_periodic_percent,
                6,
            )
            if irr_periodic_percent
            is not None
            else None
        ),
        irr_annualized_percent=(
            round(
                irr_annualized_percent,
                6,
            )
            if irr_annualized_percent
            is not None
            else None
        ),
        irr_status=irr_status,
        irr_note=irr_note,
        simple_payback_periods=(
            simple_payback
        ),
        discounted_payback_periods=(
            discounted_payback
        ),
        schedule=schedule,
        limitations=limitations,
    )


def compare_cash_flow_scenarios(
    *,
    scenarios: list[dict[str, Any]],
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit,
) -> ScenarioComparisonResult:
    if not scenarios:
        raise ValueError(
            "At least one scenario is required."
        )

    if len(scenarios) > MAX_SCENARIOS:
        raise ValueError(
            f"No more than {MAX_SCENARIOS} scenarios may be compared at once."
        )

    results: list[
        ScenarioFinanceResult
    ] = []

    seen_names: set[str] = set()

    for scenario in scenarios:
        name = str(
            scenario.get(
                "name",
                ""
            )
        ).strip()

        key = name.casefold()

        if key in seen_names:
            raise ValueError(
                f"Scenario names must be unique; duplicate: {name!r}."
            )

        seen_names.add(
            key
        )

        result = calculate_variable_cash_flow_scenario(
            name=name,
            initial_investment=float(
                scenario[
                    "initial_investment"
                ]
            ),
            cash_flows=[
                float(value)
                for value in scenario[
                    "cash_flows"
                ]
            ],
            annual_discount_rate_percent=float(
                annual_discount_rate_percent
            ),
            period_unit=period_unit,
            working_capital_outflow=float(
                scenario.get(
                    "working_capital_outflow",
                    0.0,
                )
            ),
            working_capital_recovery=float(
                scenario.get(
                    "working_capital_recovery",
                    0.0,
                )
            ),
            terminal_value=float(
                scenario.get(
                    "terminal_value",
                    0.0,
                )
            ),
        )

        results.append(
            result
        )

    ranked = sorted(
        results,
        key=lambda item: (
            item.npv,
            (
                item.profitability_index
                if item.profitability_index
                is not None
                else float("-inf")
            ),
        ),
        reverse=True,
    )

    ranking = [
        {
            "rank": index,
            "name": result.name,
            "npv": result.npv,
            "profitability_index": result.profitability_index,
            "irr_annualized_percent": result.irr_annualized_percent,
            "irr_status": result.irr_status,
            "discounted_payback_periods": result.discounted_payback_periods,
        }
        for index, result
        in enumerate(
            ranked,
            start=1,
        )
    ]

    comparison_notes = [
        (
            "Scenarios are ranked primarily by NPV at the common supplied "
            "discount rate."
        ),
        (
            "Ranking does not represent probability, strategic fit, or management "
            "approval."
        ),
        (
            "All scenarios should use assumptions that are comparable in scope "
            "and timing before management interprets the ranking."
        ),
        (
            "IRR is shown only when the individual scenario cash-flow pattern "
            "supports a unique IRR."
        ),
    ]

    return ScenarioComparisonResult(
        ranking_method=(
            "npv_desc_then_profitability_index_desc"
        ),
        scenario_count=len(
            results
        ),
        period_unit=period_unit,
        annual_discount_rate_percent=round(
            float(
                annual_discount_rate_percent
            ),
            6,
        ),
        ranking=ranking,
        scenarios=results,
        comparison_notes=comparison_notes,
    )


def scenario_result_to_dict(
    result: ScenarioFinanceResult,
) -> dict[str, Any]:
    return asdict(
        result
    )


def scenario_comparison_to_dict(
    result: ScenarioComparisonResult,
) -> dict[str, Any]:
    return asdict(
        result
    )

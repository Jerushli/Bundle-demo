from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.dcf_engine import (
    DCFResult,
    calculate_dcf,
)


@dataclass(frozen=True)
class AdvancedFinanceMetrics:
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
    simple_break_even_achieved: bool
    discounted_break_even_achieved: bool
    period_unit: str
    periods: int
    total_initial_outflow: float
    present_value_future_cash_flows: float
    total_undiscounted_future_cash_flow: float
    assumptions: dict[str, Any]
    limitations: list[str]


def _cash_flow_series(
    result: DCFResult,
) -> list[float]:
    return [
        -float(
            result.total_initial_outflow
        ),
        *[
            float(
                row.total_cash_flow
            )
            for row in result.cash_flows
        ],
    ]


def _sign_changes(
    values: list[float],
) -> int:
    non_zero = [
        value
        for value in values
        if abs(
            value
        ) > 1e-12
    ]

    if len(
        non_zero
    ) < 2:
        return 0

    changes = 0

    previous_positive = (
        non_zero[0] > 0
    )

    for value in non_zero[1:]:
        current_positive = (
            value > 0
        )

        if (
            current_positive
            != previous_positive
        ):
            changes += 1

        previous_positive = (
            current_positive
        )

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
        in enumerate(
            cash_flows
        )
    )


def _solve_irr_bisection(
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
                "IRR is unavailable because the cash-flow series does not "
                "contain both negative and positive cash flows."
            ),
        )

    if changes > 1:
        return (
            None,
            "ambiguous",
            (
                "IRR is not reported because the cash-flow series changes sign "
                "more than once and may have multiple IRR solutions."
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

    # Expand upper bound until we bracket a root or reach a safety ceiling.
    safety_upper = 1_000_000.0

    while (
        f_lower
        * f_upper
        > 0
        and upper < safety_upper
    ):
        upper *= 2.0

        f_upper = _npv_at_rate(
            cash_flows,
            upper,
        )

    if (
        f_lower
        * f_upper
        > 0
    ):
        return (
            None,
            "not_bracketed",
            (
                "IRR could not be bracketed within the configured numerical "
                "search range."
            ),
        )

    for _ in range(
        250
    ):
        midpoint = (
            lower
            + upper
        ) / 2.0

        f_mid = _npv_at_rate(
            cash_flows,
            midpoint,
        )

        if abs(
            f_mid
        ) < 1e-8:
            return (
                midpoint,
                "available",
                (
                    "IRR is the periodic discount rate that makes NPV "
                    "approximately zero."
                ),
            )

        if (
            f_lower
            * f_mid
            <= 0
        ):
            upper = midpoint
            f_upper = f_mid

        else:
            lower = midpoint
            f_lower = f_mid

    midpoint = (
        lower
        + upper
    ) / 2.0

    return (
        midpoint,
        "available",
        (
            "IRR was solved numerically using deterministic bisection."
        ),
    )


def calculate_advanced_metrics_from_dcf(
    result: DCFResult,
) -> AdvancedFinanceMetrics:
    initial = float(
        result.total_initial_outflow
    )

    pv_future = float(
        result.present_value_future_cash_flows
    )

    total_future = float(
        result.total_undiscounted_future_cash_flow
    )

    profitability_index = (
        pv_future
        / initial
        if initial > 0
        else None
    )

    simple_return_multiple = (
        total_future
        / initial
        if initial > 0
        else None
    )

    simple_roi_percent = (
        (
            total_future
            - initial
        )
        / initial
        * 100.0
        if initial > 0
        else None
    )

    cash_flows = _cash_flow_series(
        result
    )

    irr_periodic, irr_status, irr_note = (
        _solve_irr_bisection(
            cash_flows
        )
    )

    irr_periodic_percent: float | None = None
    irr_annualized_percent: float | None = None

    if irr_periodic is not None:
        irr_periodic_percent = (
            irr_periodic
            * 100.0
        )

        if result.period_unit == "monthly":
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

    assumptions = {
        "irr_method": (
            "deterministic_bisection"
        ),
        "irr_definition": (
            "Periodic rate that sets NPV of the complete supplied cash-flow "
            "series to approximately zero."
        ),
        "monthly_irr_annualization": (
            "(1 + monthly_irr)^12 - 1"
        ),
        "profitability_index_definition": (
            "present value of future cash flows / total initial outflow"
        ),
        "simple_return_multiple_definition": (
            "total undiscounted future cash flow / total initial outflow"
        ),
        "simple_roi_definition": (
            "(total undiscounted future cash flow - total initial outflow) "
            "/ total initial outflow"
        ),
    }

    limitations = [
        (
            "IRR is calculated only when the supplied cash-flow pattern has "
            "exactly one sign change."
        ),
        (
            "Multiple-sign-change cash-flow patterns may have multiple IRRs, "
            "so Bundle intentionally does not report a single IRR for them."
        ),
        (
            "Profitability index and ROI are deterministic outputs from the "
            "supplied assumptions, not predictions of project performance."
        ),
        (
            "Simple ROI ignores the timing of cash flows; NPV and IRR account "
            "for timing through discounting."
        ),
        (
            "IRR should be interpreted together with NPV rather than used as "
            "the sole investment criterion."
        ),
    ]

    return AdvancedFinanceMetrics(
        npv=round(
            float(
                result.npv
            ),
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
            result.simple_payback_periods
        ),
        discounted_payback_periods=(
            result.discounted_payback_periods
        ),
        simple_break_even_achieved=(
            result.simple_payback_periods
            is not None
        ),
        discounted_break_even_achieved=(
            result.discounted_payback_periods
            is not None
        ),
        period_unit=(
            result.period_unit
        ),
        periods=(
            result.periods
        ),
        total_initial_outflow=round(
            initial,
            2,
        ),
        present_value_future_cash_flows=round(
            pv_future,
            2,
        ),
        total_undiscounted_future_cash_flow=round(
            total_future,
            2,
        ),
        assumptions=assumptions,
        limitations=limitations,
    )


def calculate_advanced_finance_metrics(
    *,
    initial_investment: float,
    periodic_cash_flow: float,
    periods: int,
    annual_discount_rate_percent: float,
    period_unit: str = "yearly",
    working_capital_outflow: float = 0.0,
    working_capital_recovery: float = 0.0,
    terminal_value: float = 0.0,
) -> tuple[
    DCFResult,
    AdvancedFinanceMetrics,
]:
    result = calculate_dcf(
        initial_investment=initial_investment,
        periodic_cash_flow=periodic_cash_flow,
        periods=periods,
        annual_discount_rate_percent=annual_discount_rate_percent,
        period_unit=period_unit,
        working_capital_outflow=working_capital_outflow,
        working_capital_recovery=working_capital_recovery,
        terminal_value=terminal_value,
    )

    metrics = calculate_advanced_metrics_from_dcf(
        result
    )

    return (
        result,
        metrics,
    )


def advanced_metrics_to_dict(
    metrics: AdvancedFinanceMetrics,
) -> dict[str, Any]:
    return asdict(
        metrics
    )

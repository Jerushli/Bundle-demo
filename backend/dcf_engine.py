from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


PeriodUnit = Literal[
    "monthly",
    "yearly",
]

MAX_INITIAL_INVESTMENT = 1_000_000_000_000.0
MAX_ABSOLUTE_CASH_FLOW = 1_000_000_000_000.0
MAX_PERIODS = 600
MAX_DISCOUNT_RATE_PERCENT = 500.0


@dataclass(frozen=True)
class DiscountedCashFlowRow:
    period: int
    period_label: str
    recurring_cash_flow: float
    working_capital_recovery: float
    terminal_value: float
    total_cash_flow: float
    discount_factor: float
    discounted_cash_flow: float
    cumulative_cash_flow: float
    cumulative_discounted_cash_flow: float


@dataclass(frozen=True)
class DCFResult:
    initial_investment: float
    working_capital_outflow: float
    total_initial_outflow: float
    periodic_cash_flow: float
    periods: int
    period_unit: PeriodUnit
    annual_discount_rate_percent: float
    periodic_discount_rate_percent: float
    working_capital_recovery: float
    terminal_value: float
    total_undiscounted_future_cash_flow: float
    net_undiscounted_benefit: float
    present_value_future_cash_flows: float
    npv: float
    simple_payback_periods: int | None
    discounted_payback_periods: int | None
    npv_positive: bool
    cash_flows: list[DiscountedCashFlowRow]
    assumptions: dict[str, Any]
    limitations: list[str]


def _validate_inputs(
    *,
    initial_investment: float,
    periodic_cash_flow: float,
    periods: int,
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit,
    working_capital_outflow: float,
    working_capital_recovery: float,
    terminal_value: float,
):
    if initial_investment <= 0:
        raise ValueError(
            "initial_investment must be greater than zero."
        )

    if initial_investment > MAX_INITIAL_INVESTMENT:
        raise ValueError(
            "initial_investment exceeds the configured safety limit."
        )

    for name, value in {
        "periodic_cash_flow": periodic_cash_flow,
        "working_capital_outflow": working_capital_outflow,
        "working_capital_recovery": working_capital_recovery,
        "terminal_value": terminal_value,
    }.items():
        if abs(float(value)) > MAX_ABSOLUTE_CASH_FLOW:
            raise ValueError(
                f"{name} exceeds the configured safety limit."
            )

    if periods < 1 or periods > MAX_PERIODS:
        raise ValueError(
            f"periods must be between 1 and {MAX_PERIODS}."
        )

    if (
        annual_discount_rate_percent < 0
        or annual_discount_rate_percent > MAX_DISCOUNT_RATE_PERCENT
    ):
        raise ValueError(
            "annual_discount_rate_percent must be between 0 and 500."
        )

    if period_unit not in {
        "monthly",
        "yearly",
    }:
        raise ValueError(
            "period_unit must be 'monthly' or 'yearly'."
        )

    if working_capital_outflow < 0:
        raise ValueError(
            "working_capital_outflow cannot be negative."
        )

    if working_capital_recovery < 0:
        raise ValueError(
            "working_capital_recovery cannot be negative."
        )

    if terminal_value < 0:
        raise ValueError(
            "terminal_value cannot be negative."
        )


def _periodic_rate(
    *,
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit,
) -> float:
    annual_rate = (
        float(
            annual_discount_rate_percent
        )
        / 100.0
    )

    if period_unit == "yearly":
        return annual_rate

    return (
        (1.0 + annual_rate)
        ** (1.0 / 12.0)
        - 1.0
    )


def calculate_dcf(
    *,
    initial_investment: float,
    periodic_cash_flow: float,
    periods: int,
    annual_discount_rate_percent: float,
    period_unit: PeriodUnit = "yearly",
    working_capital_outflow: float = 0.0,
    working_capital_recovery: float = 0.0,
    terminal_value: float = 0.0,
) -> DCFResult:
    _validate_inputs(
        initial_investment=float(
            initial_investment
        ),
        periodic_cash_flow=float(
            periodic_cash_flow
        ),
        periods=int(
            periods
        ),
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

    initial_investment = float(
        initial_investment
    )
    periodic_cash_flow = float(
        periodic_cash_flow
    )
    periods = int(
        periods
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

    rate = _periodic_rate(
        annual_discount_rate_percent=float(
            annual_discount_rate_percent
        ),
        period_unit=period_unit,
    )

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

    simple_payback: int | None = None
    discounted_payback: int | None = None

    schedule: list[
        DiscountedCashFlowRow
    ] = []

    total_future = 0.0
    pv_future = 0.0

    for period in range(
        1,
        periods + 1,
    ):
        final_period = (
            period == periods
        )

        wc_recovery = (
            working_capital_recovery
            if final_period
            else 0.0
        )

        period_terminal_value = (
            terminal_value
            if final_period
            else 0.0
        )

        total_cash_flow = (
            periodic_cash_flow
            + wc_recovery
            + period_terminal_value
        )

        discount_factor = (
            1.0
            / (
                (1.0 + rate)
                ** period
            )
        )

        discounted_cash_flow = (
            total_cash_flow
            * discount_factor
        )

        total_future += (
            total_cash_flow
        )

        pv_future += (
            discounted_cash_flow
        )

        cumulative += (
            total_cash_flow
        )

        cumulative_discounted += (
            discounted_cash_flow
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
            DiscountedCashFlowRow(
                period=period,
                period_label=(
                    f"Month {period}"
                    if period_unit
                    == "monthly"
                    else f"Year {period}"
                ),
                recurring_cash_flow=round(
                    periodic_cash_flow,
                    2,
                ),
                working_capital_recovery=round(
                    wc_recovery,
                    2,
                ),
                terminal_value=round(
                    period_terminal_value,
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
                    discounted_cash_flow,
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

    net_undiscounted = (
        total_future
        - total_initial_outflow
    )

    assumptions = {
        "cash_flow_timing": (
            "Recurring cash flow is assumed to occur at the end of each period."
        ),
        "discount_rate_input": (
            "annual_effective_rate"
        ),
        "working_capital_timing": (
            "Working-capital outflow occurs at time 0; recovery occurs at the end "
            "of the final period."
        ),
        "terminal_value_timing": (
            "Terminal value, when supplied, occurs at the end of the final period."
        ),
    }

    limitations = [
        (
            "This is a deterministic DCF calculation using explicitly supplied "
            "cash-flow assumptions; it is not a forecast of future cash flows."
        ),
        (
            "Recurring cash flow is constant across all periods in Stage 17.1."
        ),
        (
            "The model does not yet support a different cash-flow amount for each "
            "individual period."
        ),
        (
            "Tax, depreciation, financing structure, inflation, and currency "
            "effects are not modeled unless already reflected in the supplied "
            "cash-flow values."
        ),
        (
            "Terminal value and working-capital recovery are explicit assumptions "
            "and are not estimated by the LLM."
        ),
        (
            "A positive NPV means the supplied scenario creates value at the "
            "specified discount rate; it does not guarantee the project will "
            "achieve those cash flows."
        ),
    ]

    return DCFResult(
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
        periodic_cash_flow=round(
            periodic_cash_flow,
            2,
        ),
        periods=periods,
        period_unit=period_unit,
        annual_discount_rate_percent=round(
            float(
                annual_discount_rate_percent
            ),
            6,
        ),
        periodic_discount_rate_percent=round(
            rate
            * 100.0,
            8,
        ),
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
        net_undiscounted_benefit=round(
            net_undiscounted,
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
        simple_payback_periods=(
            simple_payback
        ),
        discounted_payback_periods=(
            discounted_payback
        ),
        npv_positive=(
            npv > 0
        ),
        cash_flows=schedule,
        assumptions=assumptions,
        limitations=limitations,
    )


def dcf_result_to_dict(
    result: DCFResult,
) -> dict[str, Any]:
    return asdict(
        result
    )

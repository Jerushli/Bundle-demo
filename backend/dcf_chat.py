from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dcf_engine import (
    calculate_dcf,
    dcf_result_to_dict,
)


load_dotenv(
    override=True
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing."
    )

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

client = Groq(
    api_key=GROQ_API_KEY.strip(),
    timeout=30.0,
)


DCF_MARKERS = (
    "npv",
    "net present value",
    "discounted cash flow",
    "discounted cashflow",
    "dcf",
    "discount rate",
    "present value",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def should_use_dcf(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    if any(
        marker in q
        for marker in DCF_MARKERS
    ):
        return True

    # Conservative fallback: explicit investment + recurring cash flow + time.
    return (
        (
            "invest" in q
            or "investment" in q
        )
        and (
            "cash flow" in q
            or "cashflow" in q
        )
        and (
            "year" in q
            or "month" in q
        )
    )


def _money_multiplier(
    unit: str | None,
) -> float:
    if not unit:
        return 1.0

    unit = unit.lower()

    if unit in {
        "crore",
        "crores",
        "cr",
    }:
        return 10_000_000.0

    if unit in {
        "lakh",
        "lakhs",
        "lac",
        "lacs",
    }:
        return 100_000.0

    if unit in {
        "million",
        "m",
    }:
        return 1_000_000.0

    if unit in {
        "billion",
        "bn",
    }:
        return 1_000_000_000.0

    return 1.0


MONEY_CAPTURE = (
    r"(?:₹|inr|rs\.?)?\s*"
    r"([\d,.]+)"
    r"\s*"
    r"(crores?|cr|lakhs?|lacs?|million|billion|m|bn)?"
)


def _money_from_match(
    match: re.Match[str],
    amount_group: int,
    unit_group: int,
) -> float:
    raw = (
        match.group(
            amount_group
        )
        .replace(
            ",",
            "",
        )
    )

    value = float(
        raw
    )

    unit = match.group(
        unit_group
    )

    return (
        value
        * _money_multiplier(
            unit
        )
    )


def _extract_initial_investment(
    question: str,
) -> float | None:
    q = _normalize(
        question
    )

    patterns = [
        (
            rf"(?:initial\s+investment|investment(?:\s+of)?|invest)"
            rf"(?:\s+is|\s+of|\s*=)?\s*{MONEY_CAPTURE}"
        ),
        (
            rf"{MONEY_CAPTURE}\s+(?:initial\s+investment|investment)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if match:
            return _money_from_match(
                match,
                1,
                2,
            )

    return None


def _extract_periodic_cash_flow(
    question: str,
) -> float | None:
    q = _normalize(
        question
    )

    patterns = [
        (
            rf"(?:periodic|annual|yearly|monthly|recurring|incremental)?\s*"
            rf"(?:cash\s*flow|cashflow)"
            rf"(?:\s+of|\s+is|\s*=)?\s*"
            rf"{MONEY_CAPTURE}"
        ),
        (
            rf"(?:receive|generate|earn|expect)"
            rf".{{0,25}}?"
            rf"{MONEY_CAPTURE}"
            rf"\s*(?:per\s+(?:year|month)|annually|monthly)?"
            rf".{{0,20}}?"
            rf"(?:cash\s*flow|cashflow)?"
        ),
        (
            rf"{MONEY_CAPTURE}"
            rf"\s+(?:annual|yearly|monthly|recurring|periodic)\s+"
            rf"(?:cash\s*flow|cashflow)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if match:
            return _money_from_match(
                match,
                1,
                2,
            )

    return None


def _extract_periods_and_unit(
    question: str,
) -> tuple[
    int | None,
    str | None,
]:
    q = _normalize(
        question
    )

    # Explicit duration is preferred.
    match = re.search(
        r"(?:for|over|across|during)\s+(\d+)\s+years?\b",
        q,
    )

    if match:
        return (
            int(
                match.group(1)
            ),
            "yearly",
        )

    match = re.search(
        r"(?:for|over|across|during)\s+(\d+)\s+months?\b",
        q,
    )

    if match:
        return (
            int(
                match.group(1)
            ),
            "monthly",
        )

    match = re.search(
        r"(\d+)[-\s]?year\s+(?:dcf|period|horizon|project|scenario)\b",
        q,
    )

    if match:
        return (
            int(
                match.group(1)
            ),
            "yearly",
        )

    match = re.search(
        r"(\d+)[-\s]?month\s+(?:dcf|period|horizon|project|scenario)\b",
        q,
    )

    if match:
        return (
            int(
                match.group(1)
            ),
            "monthly",
        )

    return (
        None,
        None,
    )


def _extract_discount_rate(
    question: str,
) -> float | None:
    q = _normalize(
        question
    )

    patterns = [
        (
            r"(?:annual\s+)?discount\s+rate"
            r"(?:\s+of|\s+is|\s*=)?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
        ),
        (
            r"(?:at|using|with)\s+(?:a\s+)?"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
            r"\s+(?:annual\s+)?discount\s+rate"
        ),
        (
            r"(?:discounted|discount)\s+at\s+"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            q,
        )

        if match:
            return float(
                match.group(1)
            )

    return None


def _extract_terminal_value(
    question: str,
) -> float:
    q = _normalize(
        question
    )

    pattern = (
        rf"terminal\s+value"
        rf"(?:\s+of|\s+is|\s*=)?\s*"
        rf"{MONEY_CAPTURE}"
    )

    match = re.search(
        pattern,
        q,
        flags=re.IGNORECASE,
    )

    if not match:
        return 0.0

    return _money_from_match(
        match,
        1,
        2,
    )


def _extract_working_capital_outflow(
    question: str,
) -> float:
    q = _normalize(
        question
    )

    patterns = [
        (
            rf"(?:initial\s+)?working\s+capital"
            rf"(?:\s+outflow)?"
            rf"(?:\s+of|\s+is|\s*=)?\s*"
            rf"{MONEY_CAPTURE}"
        ),
        (
            rf"working\s+capital\s+outflow"
            rf".{{0,12}}?"
            rf"{MONEY_CAPTURE}"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if match:
            return _money_from_match(
                match,
                1,
                2,
            )

    return 0.0


def _extract_working_capital_recovery(
    question: str,
) -> float:
    q = _normalize(
        question
    )

    patterns = [
        (
            rf"working\s+capital\s+recovery"
            rf"(?:\s+of|\s+is|\s*=)?\s*"
            rf"{MONEY_CAPTURE}"
        ),
        (
            rf"recover(?:y|ed)?"
            rf".{{0,20}}?"
            rf"{MONEY_CAPTURE}"
            rf".{{0,20}}?"
            rf"working\s+capital"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            q,
            flags=re.IGNORECASE,
        )

        if match:
            return _money_from_match(
                match,
                1,
                2,
            )

    return 0.0


def _requirements(
    *,
    question: str,
    missing: list[str],
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**DCF calculation needs more explicit assumptions.** "
            "I will not invent the missing values. Please provide: "
            + ", ".join(
                missing
            )
            + ". Terminal value and working-capital assumptions are optional "
            "and default to zero when omitted."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "dcf",
        "tool_name": "dcf_requirements",
        "answer_mode": answer_mode,
        "dcf": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
        },
    }


def _fallback_answer(
    result: dict[str, Any],
) -> str:
    npv = float(
        result[
            "npv"
        ]
    )

    sign_text = (
        "positive"
        if npv > 0
        else (
            "negative"
            if npv < 0
            else "zero"
        )
    )

    discounted_payback = result.get(
        "discounted_payback_periods"
    )

    payback_text = (
        f"{discounted_payback} {result['period_unit']} periods"
        if discounted_payback
        is not None
        else "not achieved within the modeled horizon"
    )

    return (
        f"**DCF result:** NPV is {npv:,.2f}, which is {sign_text} under the "
        f"supplied assumptions. Present value of future cash flows is "
        f"{result['present_value_future_cash_flows']:,.2f} against an initial "
        f"outflow of {result['total_initial_outflow']:,.2f}. Discounted payback "
        f"is {payback_text}. These are deterministic results from the supplied "
        "cash-flow assumptions, not predictions of future cash flows."
    )


def _explain(
    *,
    question: str,
    result: dict[str, Any],
    answer_mode: str,
) -> str:
    style = (
        "Give a concise executive explanation in 5 to 7 sentences."
        if answer_mode
        == "summary"
        else (
            "Give a detailed explanation with sections for Initial Outflow, "
            "Cash-Flow Assumptions, Discounting, NPV, Payback, Limitations, "
            "and Bottom Line."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining a deterministic discounted-cash-flow
calculation.

Rules:
1. Use every supplied number exactly as provided by the deterministic engine.
2. Never recalculate or alter the NPV.
3. Clearly label future cash flows, working capital, and terminal value as
   explicit scenario assumptions, not predictions.
4. Explain that the discount rate is an assumption/input.
5. A positive NPV means value creation only under the supplied assumptions.
6. A negative NPV means the scenario does not recover the required return under
   the supplied assumptions.
7. Do not invent IRR, tax, depreciation, financing effects, inflation, or any
   metric absent from the result.
8. Do not claim that management should automatically approve an investment.
9. If payback is unavailable, say it is not achieved within the modeled horizon.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

DETERMINISTIC DCF RESULT

{json.dumps(result, ensure_ascii=False, indent=2)}
""".strip()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0,
        )

        answer = (
            response.choices[0]
            .message.content
            or ""
        ).strip()

        if answer:
            return answer

    except Exception:
        pass

    return _fallback_answer(
        result
    )


def process_dcf_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    initial_investment = (
        _extract_initial_investment(
            question
        )
    )

    periodic_cash_flow = (
        _extract_periodic_cash_flow(
            question
        )
    )

    periods, period_unit = (
        _extract_periods_and_unit(
            question
        )
    )

    discount_rate = (
        _extract_discount_rate(
            question
        )
    )

    terminal_value = (
        _extract_terminal_value(
            question
        )
    )

    working_capital_outflow = (
        _extract_working_capital_outflow(
            question
        )
    )

    working_capital_recovery = (
        _extract_working_capital_recovery(
            question
        )
    )

    missing: list[str] = []

    if initial_investment is None:
        missing.append(
            "initial investment amount"
        )

    if periodic_cash_flow is None:
        missing.append(
            "recurring periodic cash-flow amount"
        )

    if (
        periods is None
        or period_unit is None
    ):
        missing.append(
            "modeled duration in months or years"
        )

    if discount_rate is None:
        missing.append(
            "annual discount rate percentage"
        )

    if missing:
        return _requirements(
            question=question,
            missing=missing,
            answer_mode=answer_mode,
        )

    result = calculate_dcf(
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
            discount_rate
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

    payload = dcf_result_to_dict(
        result
    )

    rows = [
        {
            "group_name": "Initial outflow",
            "value": (
                result.total_initial_outflow
            ),
        },
        {
            "group_name": (
                "PV future cash flows"
            ),
            "value": (
                result.present_value_future_cash_flows
            ),
        },
        {
            "group_name": "NPV",
            "value": result.npv,
        },
    ]

    return {
        "answer": _explain(
            question=question,
            result=payload,
            answer_mode=answer_mode,
        ),
        "rows": rows,
        "group_by": "dcf",
        "metric": "amount",
        "source": "dcf",
        "tool_name": "dcf_engine",
        "answer_mode": answer_mode,
        "dcf": payload,
        "evidence": payload,
    }

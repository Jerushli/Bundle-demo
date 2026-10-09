from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dataset_analytics import get_category_value_matches
from backend.investment_model import (
    calculate_investment_scenario,
    investment_result_to_dict,
)

load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing.")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=GROQ_API_KEY.strip(), timeout=30.0)

INVESTMENT_MARKERS = (
    "if we invest",
    "if i invest",
    "investment of",
    "invest ₹",
    "invest rs",
    "invest inr",
    "put ₹",
    "put rs",
    "put inr",
)

def _normalize(value: str) -> str:
    return " ".join(value.lower().split())

def should_use_investment_scenario(*, question: str, role: str) -> bool:
    q = _normalize(question)
    return any(marker in q for marker in INVESTMENT_MARKERS)

def _money_multiplier(unit: str | None) -> float:
    if not unit:
        return 1.0
    unit = unit.lower()
    if unit in {"crore", "crores", "cr"}:
        return 10_000_000.0
    if unit in {"lakh", "lakhs", "lac", "lacs"}:
        return 100_000.0
    if unit in {"million", "m"}:
        return 1_000_000.0
    if unit in {"billion", "bn"}:
        return 1_000_000_000.0
    return 1.0

def _extract_investment_amount(question: str) -> float | None:
    q = _normalize(question)
    patterns = [
        r"(?:₹|inr|rs\.?)\s*([\d,.]+)\s*(crores?|cr|lakhs?|lacs?|million|billion|m|bn)?",
        r"\binvest(?:ment)?(?:\s+of)?\s+([\d,.]+)\s*(crores?|cr|lakhs?|lacs?|million|billion|m|bn)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, q, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1).replace(",", ""))
            unit = match.group(2) if len(match.groups()) >= 2 else None
            return value * _money_multiplier(unit)
    return None

def _extract_target(*, question: str, role: str) -> tuple[str | None, str | None]:
    matches = get_category_value_matches(question, role=role)
    for column in ("region", "country", "product", "segment", "department", "channel", "category"):
        values = matches.get(column)
        if values and len(values) == 1:
            return column, values[0]
    singles = [(column, values[0]) for column, values in matches.items() if len(values) == 1]
    return singles[0] if len(singles) == 1 else (None, None)

def _extract_uplift(question: str) -> tuple[str | None, float | None]:
    q = _normalize(question)
    match = re.search(
        r"\b(sales|revenue)\b.{0,45}?\b(increase|increases|rise|rises|grow|grows|uplift)\b"
        r".{0,20}?([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)",
        q,
    )
    if match:
        return "sales", float(match.group(3))
    match = re.search(
        r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b).{0,20}?\b(sales|revenue)\b"
        r".{0,20}?\b(uplift|increase|growth)\b",
        q,
    )
    if match:
        return "sales", float(match.group(1))
    return None, None

def _extract_margin(question: str) -> float | None:
    q = _normalize(question)
    patterns = [
        r"(?:incremental|contribution)\s+margin(?:\s+is|\s+of|\s*=)?\s*([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)",
        r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)\s+(?:incremental|contribution)\s+margin",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return float(match.group(1))
    return None

def _extract_horizon(question: str) -> int | None:
    q = _normalize(question)
    for pattern in (
        r"(?:over|for|within)\s+(\d+)\s+months?\b",
        r"horizon(?:\s+of|\s*=)?\s*(\d+)\s+months?\b",
    ):
        match = re.search(pattern, q)
        if match:
            return int(match.group(1))
    if "over 1 year" in q or "for 1 year" in q:
        return 12
    return None

def _extract_baseline_period(question: str) -> int | None:
    q = _normalize(question)
    for pattern in (
        r"(?:using|with|based on)\s+(?:(?:a|the)\s+)?(?:last\s+)?(\d+)[-\s]?month\s+baseline",
        r"baseline(?:\s+period)?(?:\s+of|\s*=)?\s*(\d+)\s+months?\b",
    ):
        match = re.search(pattern, q)
        if match:
            return int(match.group(1))
    return None

def _extract_hurdle_rate(question: str) -> float | None:
    q = _normalize(question)
    patterns = [
        r"(?:minimum|min|required|hurdle)\s+(?:acceptable\s+)?(?:roi|return|hurdle rate)"
        r"(?:\s+is|\s+of|\s*=)?\s*([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)",
        r"hurdle rate(?:\s+is|\s+of|\s*=)?\s*([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return float(match.group(1))
    return None

def _extract_max_payback(question: str) -> float | None:
    q = _normalize(question)
    patterns = [
        r"(?:maximum|max)\s+(?:acceptable\s+)?payback(?:\s+is|\s+of|\s*=)?\s*(\d+(?:\.\d+)?)\s+months?\b",
        r"payback(?:\s+limit)?(?:\s+is|\s+of|\s*=)?\s*(\d+(?:\.\d+)?)\s+months?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return float(match.group(1))
    return None

def _requirements(question: str, missing: list[str], answer_mode: str) -> dict[str, Any]:
    return {
        "answer": (
            "**Investment scenario needs more explicit assumptions.** "
            "I will not invent the missing values. Please provide: "
            + ", ".join(missing) + "."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "investment",
        "tool_name": "investment_requirements",
        "answer_mode": answer_mode,
        "investment": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
        },
    }

def _fallback(result: dict[str, Any]) -> str:
    payback = (
        f"{result['payback_months']:.2f} months"
        if result["payback_months"] is not None
        else "not achievable"
    )
    return (
        f"**Scenario result:** {result['rule_result'].replace('_', ' ').title()}. "
        f"Under the supplied assumptions, incremental operating profit is "
        f"{result['incremental_operating_profit']:,.2f}, ROI is "
        f"{result['roi_percent']:.2f}%, and payback is {payback}. "
        "This is a deterministic scenario based on explicit assumptions, not a causal prediction."
    )

def _explain(*, question: str, result: dict[str, Any], answer_mode: str) -> str:
    style = (
        "Give a concise executive explanation in 5 to 7 sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed explanation with sections for Observed Baseline, "
            "Explicit Assumptions, Economics, Business Rules, Limitations, and Bottom Line."
        )
    )
    system_prompt = """
You are Bundle Data Assistant explaining a deterministic investment scenario.

Rules:
1. Use the supplied numbers exactly.
2. Separate observed database facts from user-supplied assumptions.
3. Never describe uplift or margin assumptions as predictions.
4. State ROI/payback as hypothetical scenario results only.
5. State whether hurdle-rate and payback rules pass.
6. Do not invent NPV, IRR, tax, financing cost, or any absent metric.
7. Passing rules does not authorize the investment.
8. If rules fail, say the scenario fails under the supplied assumptions.
9. If rules pass, call it economically favorable under the supplied assumptions,
   not guaranteed future performance.
""".strip()
    user_prompt = f"""
QUESTION
{question}

STYLE
{style}

DETERMINISTIC INVESTMENT RESULT
{json.dumps(result, ensure_ascii=False, indent=2)}
""".strip()
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        answer = (response.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception:
        pass
    return _fallback(result)

def process_investment_chat(*, question: str, role: str, answer_mode: str = "summary") -> dict[str, Any]:
    target_column, target_value = _extract_target(question=question, role=role)
    investment_amount = _extract_investment_amount(question)
    baseline_measure, uplift = _extract_uplift(question)
    margin = _extract_margin(question)
    horizon = _extract_horizon(question)
    baseline_period = _extract_baseline_period(question)
    hurdle = _extract_hurdle_rate(question)
    max_payback = _extract_max_payback(question)

    missing: list[str] = []
    if target_column is None or target_value is None:
        missing.append("one specific target such as region/product")
    if investment_amount is None:
        missing.append("investment amount")
    if baseline_measure is None or uplift is None:
        missing.append("explicit sales/revenue uplift percentage")
    if margin is None:
        missing.append("incremental/contribution margin percentage")
    if horizon is None:
        missing.append("scenario horizon in months")
    if baseline_period is None:
        missing.append("baseline period in months")
    if hurdle is None:
        missing.append("minimum ROI / hurdle rate percentage")
    if max_payback is None:
        missing.append("maximum acceptable payback in months")

    if missing:
        return _requirements(question, missing, answer_mode)

    result = calculate_investment_scenario(
        role=role,
        target_column=target_column,
        target_value=target_value,
        investment_amount=float(investment_amount),
        expected_revenue_uplift_percent=float(uplift),
        contribution_margin_percent=float(margin),
        horizon_months=int(horizon),
        baseline_period_months=int(baseline_period),
        hurdle_rate_percent=float(hurdle),
        max_payback_months=float(max_payback),
        baseline_measure=baseline_measure,
    )

    payload = investment_result_to_dict(result)
    rows = [
        {"group_name": "Investment", "value": result.investment_amount},
        {"group_name": "Incremental operating profit", "value": result.incremental_operating_profit},
        {"group_name": "Net benefit", "value": result.net_benefit_after_investment},
    ]

    return {
        "answer": _explain(question=question, result=payload, answer_mode=answer_mode),
        "rows": rows,
        "group_by": "investment_scenario",
        "metric": "amount",
        "source": "investment",
        "tool_name": "investment_model",
        "answer_mode": answer_mode,
        "investment": payload,
        "evidence": payload,
    }

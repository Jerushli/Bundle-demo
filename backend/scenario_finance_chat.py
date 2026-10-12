from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dcf_chat import (
    _extract_discount_rate,
    _extract_initial_investment,
    _extract_terminal_value,
    _extract_working_capital_outflow,
    _extract_working_capital_recovery,
    _money_multiplier,
)
from backend.scenario_finance import (
    compare_cash_flow_scenarios,
    scenario_comparison_to_dict,
)


load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing.")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=GROQ_API_KEY.strip(), timeout=30.0)


SCENARIO_MARKERS = (
    "compare scenarios",
    "compare scenario",
    "compare conservative",
    "conservative:",
    "base:",
    "optimistic:",
    "scenario comparison",
    "compare these cases",
    "compare these scenarios",
)

KNOWN_SCENARIO_NAMES = (
    "conservative",
    "base",
    "optimistic",
    "stress",
    "downside",
    "upside",
    "bear",
    "bull",
)


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def should_use_finance_scenario_comparison(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(question)

    if any(marker in q for marker in SCENARIO_MARKERS):
        return True

    named = sum(
        1
        for name in KNOWN_SCENARIO_NAMES
        if re.search(rf"\b{re.escape(name)}\b", q)
    )

    return (
        named >= 2
        and (
            "cash flow" in q
            or "npv" in q
            or "irr" in q
            or "investment" in q
        )
    )


def _parse_money_token(token: str) -> float:
    token = token.strip().lower()

    match = re.fullmatch(
        r"(?:₹|inr|rs\.?)?\s*"
        r"([\d,.]+)\s*"
        r"(crores?|cr|lakhs?|lacs?|million|billion|m|bn)?",
        token,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            f"Could not parse cash-flow amount {token!r}."
        )

    value = float(match.group(1).replace(",", ""))
    unit = match.group(2)

    return value * _money_multiplier(unit)


def _extract_period_unit(
    question: str,
) -> str | None:
    q = _normalize(question)

    if re.search(r"\b\d+[-\s]?years?\b", q):
        return "yearly"

    if re.search(r"\b\d+[-\s]?months?\b", q):
        return "monthly"

    if "annual cash flow" in q or "yearly cash flow" in q:
        return "yearly"

    if "monthly cash flow" in q:
        return "monthly"

    return None


def _extract_named_scenario_blocks(
    question: str,
) -> list[tuple[str, str]]:
    # Accept labels on their own line or inline:
    # Conservative: ₹25L, ₹30L, ...
    # Base: ...
    # Optimistic: ...
    pattern = re.compile(
        r"(?im)^\s*([A-Za-z][A-Za-z0-9 _-]{0,40})\s*:\s*(.+?)\s*$"
    )

    rows = pattern.findall(question)

    blocks: list[tuple[str, str]] = []

    for raw_name, body in rows:
        name = raw_name.strip()

        if name.lower() in {
            "initial investment",
            "terminal value",
            "discount rate",
            "working capital",
        }:
            continue

        blocks.append((name, body.strip()))

    # Fallback for a compact single-line prompt.
    if not blocks:
        q = question
        names = [
            match
            for match in re.finditer(
                r"(?i)\b(conservative|base|optimistic|stress|downside|upside|bear|bull)\s*:",
                q,
            )
        ]

        for index, match in enumerate(names):
            start = match.end()
            end = (
                names[index + 1].start()
                if index + 1 < len(names)
                else len(q)
            )
            blocks.append(
                (
                    match.group(1).title(),
                    q[start:end].strip(" ,;\n"),
                )
            )

    return blocks


def _extract_money_list(text: str) -> list[float]:
    token_pattern = re.compile(
        r"(?:₹|inr|rs\.?)?\s*"
        r"\d[\d,.]*\s*"
        r"(?:crores?|cr|lakhs?|lacs?|million|billion|m|bn)?",
        flags=re.IGNORECASE,
    )

    tokens = [
        match.group(0).strip()
        for match in token_pattern.finditer(text)
    ]

    values: list[float] = []

    for token in tokens:
        # Avoid accidental plain year/duration captures when no currency/unit exists.
        has_currency = bool(
            re.search(r"(₹|inr|rs\.?)", token, flags=re.IGNORECASE)
        )
        has_unit = bool(
            re.search(
                r"\b(crores?|cr|lakhs?|lacs?|million|billion|m|bn)\b",
                token,
                flags=re.IGNORECASE,
            )
        )

        if not has_currency and not has_unit:
            continue

        values.append(_parse_money_token(token))

    return values


def _requirements(
    *,
    question: str,
    missing: list[str],
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**Scenario comparison needs more explicit inputs.** "
            "I will not invent missing financial assumptions. Please provide: "
            + ", ".join(missing)
            + "."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "finance_scenarios",
        "tool_name": "scenario_finance_requirements",
        "answer_mode": answer_mode,
        "finance_scenarios": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
        },
    }


def _fallback_answer(
    payload: dict[str, Any],
) -> str:
    ranking = payload.get("ranking") or []

    if not ranking:
        return (
            "The scenarios were calculated, but no ranking was available."
        )

    leader = ranking[0]

    return (
        f"**Scenario comparison:** {leader['name']} ranks first by NPV at "
        f"{float(leader['npv']):,.2f}. The ranking is based primarily on NPV "
        "at the common supplied discount rate, with profitability index only "
        "used as a secondary tie-breaker. This does not mean the highest-ranked "
        "scenario is the most likely; every cash-flow path is an explicit "
        "scenario assumption."
    )


def _explain(
    *,
    question: str,
    payload: dict[str, Any],
    answer_mode: str,
) -> str:
    style = (
        "Give a concise executive comparison in 6 to 9 sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed comparison with sections for Assumptions, Ranking, "
            "NPV Comparison, IRR Comparison, Profitability Index, Payback, "
            "Risks / Interpretation, and Bottom Line."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining a deterministic multi-scenario
financial comparison.

Rules:
1. Use the supplied deterministic results exactly.
2. Do not recalculate or alter NPV, IRR, profitability index, ROI, or payback.
3. Clearly state that every scenario cash-flow schedule is an explicit
   assumption, not a probability forecast.
4. Ranking is primarily by NPV at the common supplied discount rate.
5. A higher-ranked scenario is financially stronger under its supplied
   assumptions; it is not necessarily more likely.
6. If a scenario has irr_status other than "available", do not invent an IRR.
7. Do not claim that management should automatically approve the top scenario.
8. Point out when a scenario has negative NPV or fails discounted payback.
9. Do not invent tax, inflation, financing, strategic-fit, or probability inputs.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

DETERMINISTIC SCENARIO COMPARISON

{json.dumps(payload, ensure_ascii=False, indent=2)}
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

        answer = (
            response.choices[0]
            .message.content
            or ""
        ).strip()

        if answer:
            return answer

    except Exception:
        pass

    return _fallback_answer(payload)


def process_finance_scenario_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    initial_investment = _extract_initial_investment(question)
    discount_rate = _extract_discount_rate(question)
    period_unit = _extract_period_unit(question)
    terminal_value = _extract_terminal_value(question)
    working_capital_outflow = _extract_working_capital_outflow(question)
    working_capital_recovery = _extract_working_capital_recovery(question)

    blocks = _extract_named_scenario_blocks(question)

    scenarios: list[dict[str, Any]] = []
    invalid_names: list[str] = []

    expected_periods: int | None = None

    duration_match = re.search(
        r"(?i)\b(\d+)[-\s]?(?:year|month)s?\b",
        question,
    )

    if duration_match:
        expected_periods = int(duration_match.group(1))

    for name, body in blocks:
        cash_flows = _extract_money_list(body)

        if not cash_flows:
            invalid_names.append(name)
            continue

        if (
            expected_periods is not None
            and len(cash_flows) != expected_periods
        ):
            invalid_names.append(
                f"{name} ({len(cash_flows)} cash flows supplied; "
                f"{expected_periods} expected)"
            )
            continue

        scenarios.append(
            {
                "name": name,
                "initial_investment": initial_investment,
                "cash_flows": cash_flows,
                "working_capital_outflow": working_capital_outflow,
                "working_capital_recovery": working_capital_recovery,
                "terminal_value": terminal_value,
            }
        )

    missing: list[str] = []

    if initial_investment is None:
        missing.append("one common initial investment amount")

    if discount_rate is None:
        missing.append("annual discount rate percentage")

    if period_unit is None:
        missing.append("scenario duration in years or months")

    if len(blocks) < 2:
        missing.append(
            "at least two named scenarios with explicit cash-flow sequences"
        )

    if invalid_names:
        missing.append(
            "valid cash-flow sequence for: "
            + ", ".join(invalid_names)
        )

    if missing:
        return _requirements(
            question=question,
            missing=missing,
            answer_mode=answer_mode,
        )

    comparison = compare_cash_flow_scenarios(
        scenarios=scenarios,
        annual_discount_rate_percent=float(discount_rate),
        period_unit=period_unit,
    )

    payload = scenario_comparison_to_dict(comparison)

    rows = [
        {
            "group_name": item["name"],
            "value": item["npv"],
        }
        for item in payload["ranking"]
    ]

    return {
        "answer": _explain(
            question=question,
            payload=payload,
            answer_mode=answer_mode,
        ),
        "rows": rows,
        "group_by": "scenario",
        "metric": "npv",
        "source": "finance_scenarios",
        "tool_name": "scenario_finance",
        "answer_mode": answer_mode,
        "finance_scenarios": payload,
        "evidence": payload,
    }

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dataset_analytics import get_active_dataset_schema, get_category_value_matches
from backend.scenario_engine import ScenarioResult, scenario_to_dict, simulate_measure_percent_change

load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing.")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=GROQ_API_KEY.strip(), timeout=30.0)

SCENARIO_MARKERS = (
    "what if", "what happens if", "what would happen if", "suppose ",
    "assuming ", "assume ", "scenario", "if we increase", "if we decrease",
    "if we raise", "if we reduce", "if we invest", "if investment",
    "if budget", "if spend",
)

POSITIVE_WORDS = (
    "increase", "increases", "increased", "rise", "rises", "rose",
    "grow", "grows", "growth", "higher", "raise", "raises", "raised", "up by",
)

NEGATIVE_WORDS = (
    "decrease", "decreases", "decreased", "drop", "drops", "dropped",
    "fall", "falls", "fell", "reduce", "reduces", "reduced", "lower",
    "lowers", "down by",
)

CAUSAL_INTERVENTIONS = (
    "invest", "investment", "budget", "spend", "spending", "marketing",
    "advertising", "campaign", "hire", "hiring", "headcount", "capacity",
    "factory", "warehouse", "expansion",
)


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def should_use_scenario(*, question: str, role: str) -> bool:
    q = _normalize(question)

    if any(marker in q for marker in SCENARIO_MARKERS):
        return True

    has_percent = bool(re.search(r"[-+]?\d+(?:\.\d+)?\s*(?:%|percent\b)", q))
    has_change = any(word in q for word in POSITIVE_WORDS + NEGATIVE_WORDS)

    return bool(has_percent and has_change)


def _extract_percent(question: str) -> float | None:
    q = _normalize(question)
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)", q)

    if not match:
        return None

    value = float(match.group(1))

    if value < 0:
        return value

    if any(word in q for word in NEGATIVE_WORDS):
        return -abs(value)

    if any(word in q for word in POSITIVE_WORDS):
        return abs(value)

    return value


def _measure_aliases(measures: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}

    for measure in measures:
        output[measure.lower()] = measure
        output[measure.replace("_", " ").lower()] = measure

    preferred = {
        "sales": ("sales", "gross_sales"),
        "revenue": ("revenue", "sales", "gross_sales"),
        "profit": ("profit", "net_profit"),
        "cost": ("cost", "cogs"),
        "costs": ("cost", "cogs"),
        "discount": ("discount_amount", "discount"),
        "discounts": ("discount_amount", "discount"),
        "price": ("sale_price", "price"),
        "prices": ("sale_price", "price"),
        "units": ("units_sold", "units"),
        "quantity": ("quantity", "units_sold"),
    }

    for alias, candidates in preferred.items():
        for candidate in candidates:
            if candidate in measures:
                output[alias] = candidate
                break

    return output


def _extract_measures(*, question: str, role: str) -> list[str]:
    schema = get_active_dataset_schema(role=role)
    q = _normalize(question)
    aliases = _measure_aliases(list(schema.measures))
    matches: list[str] = []

    for phrase, measure in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", q):
            if measure not in matches:
                matches.append(measure)

    return matches


def _extract_scope(*, question: str, role: str) -> tuple[str | None, str | None]:
    matches = get_category_value_matches(question, role=role)

    for column in ("region", "country", "product", "segment", "department", "channel", "category"):
        values = matches.get(column)
        if values and len(values) == 1:
            return column, values[0]

    singles = [(column, values[0]) for column, values in matches.items() if len(values) == 1]
    return singles[0] if len(singles) == 1 else (None, None)


def _unsupported_reason(*, question: str, measures: list[str], change_percent: float | None) -> str | None:
    q = _normalize(question)

    if any(word in q for word in CAUSAL_INTERVENTIONS):
        return (
            "The question asks for the effect of an intervention such as investment, budget, "
            "spending, hiring, or expansion. Bundle does not yet have a validated causal "
            "response model mapping that intervention to sales or profit."
        )

    if change_percent is None:
        return "A numerical percentage assumption is required for the current deterministic scenario engine."

    if len(measures) == 0:
        return "The question does not identify one permitted business measure that Bundle can change directly."

    if len(measures) > 1:
        return (
            "The question references multiple business measures. A validated causal relationship "
            "between them is required before Bundle can calculate the downstream effect safely."
        )

    return None


def _requirements_response(*, question: str, reason: str, answer_mode: str) -> dict[str, Any]:
    return {
        "answer": (
            "I can treat this as a what-if question, but I cannot calculate a defensible "
            "numerical outcome yet. " + reason +
            " To model it, provide or estimate the missing response relationship, the time "
            "horizon, and relevant business constraints."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "scenario",
        "tool_name": "scenario_requirements",
        "answer_mode": answer_mode,
        "scenario": {
            "supported": False,
            "question": question,
            "reason": reason,
            "required_inputs": [
                "explicit intervention assumption",
                "validated response relationship/model",
                "time horizon",
                "relevant business constraints",
            ],
        },
    }


def _scenario_rows(result: ScenarioResult) -> list[dict[str, Any]]:
    return [
        {"group_name": "Baseline", "value": result.baseline_value},
        {"group_name": "Scenario", "value": result.projected_value},
    ]


def _fallback_summary(result: ScenarioResult) -> str:
    scope = f" for {result.group_by}={result.group_value}" if result.group_by else ""

    return (
        f"Current {result.measure}{scope} is {result.baseline_value:,.2f}. "
        f"Under the explicit assumption of {result.change_percent:+.2f}%, the scenario value "
        f"is {result.projected_value:,.2f}, a change of {result.absolute_change:+,.2f}. "
        "This is a deterministic what-if calculation, not a forecast."
    )


def _explain_scenario(*, question: str, result: ScenarioResult, answer_mode: str) -> str:
    evidence = scenario_to_dict(result)

    style = (
        "Answer in 3 to 5 concise sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed but focused explanation of the baseline, explicit assumption, "
            "calculated scenario value, absolute difference, and limitations."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining a deterministic what-if scenario.

Rules:
1. Use the supplied scenario numbers exactly.
2. Clearly distinguish BASELINE from HYPOTHETICAL SCENARIO.
3. State the user's assumption explicitly.
4. Never describe the scenario as a forecast or prediction.
5. Do not imply the assumed change will actually occur.
6. Do not infer causal effects that are not supplied by the scenario engine.
7. Mention important limitations.
8. Do not turn this response into an investment recommendation.
9. If one measure changes directly, do not claim another measure changes too.
""".strip()

    user_prompt = f"""
QUESTION
{question}

STYLE
{style}

DETERMINISTIC SCENARIO EVIDENCE
{json.dumps(evidence, ensure_ascii=False, indent=2)}
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

    return _fallback_summary(result)


def process_scenario_chat(*, question: str, role: str, answer_mode: str = "summary") -> dict[str, Any]:
    measures = _extract_measures(question=question, role=role)
    change_percent = _extract_percent(question)

    unsupported = _unsupported_reason(
        question=question,
        measures=measures,
        change_percent=change_percent,
    )

    if unsupported:
        return _requirements_response(
            question=question,
            reason=unsupported,
            answer_mode=answer_mode,
        )

    measure = measures[0]
    group_by, group_value = _extract_scope(question=question, role=role)

    result = simulate_measure_percent_change(
        role=role,
        measure=measure,
        change_percent=float(change_percent),
        group_by=group_by,
        group_value=group_value,
    )

    evidence = scenario_to_dict(result)

    return {
        "answer": _explain_scenario(
            question=question,
            result=result,
            answer_mode=answer_mode,
        ),
        "rows": _scenario_rows(result),
        "group_by": "scenario",
        "metric": result.measure,
        "source": "scenario",
        "tool_name": "scenario_engine",
        "answer_mode": answer_mode,
        "scenario": evidence,
        "evidence": evidence,
    }

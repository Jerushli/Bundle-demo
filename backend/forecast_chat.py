from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dataset_analytics import (
    get_active_dataset_schema,
)
from backend.forecast_engine import (
    ForecastResult,
    forecast_monthly_measure,
    forecast_to_dict,
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


FUTURE_MARKERS = (
    "forecast",
    "predict",
    "prediction",
    "project",
    "projection",
    "expected next",
    "expect next",
    "next month",
    "next quarter",
    "next year",
    "next 2 month",
    "next 3 month",
    "next 4 month",
    "next 5 month",
    "next 6 month",
    "next 7 month",
    "next 8 month",
    "next 9 month",
    "next 10 month",
    "next 11 month",
    "next 12 month",
    "upcoming month",
    "upcoming quarter",
    "upcoming year",
    "future profit",
    "future sales",
    "future revenue",
    "likely next",
    "could next",
    "what could",
    "what will",
    "what might",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def should_use_forecast(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    if any(
        marker in q
        for marker in FUTURE_MARKERS
    ):
        return True

    if re.search(
        r"\bnext\s+\d+\s+months?\b",
        q,
    ):
        return True

    if re.search(
        r"\b\d+\s*-\s*month\s+forecast\b",
        q,
    ):
        return True

    if re.search(
        r"\b(upcoming|future)\b",
        q,
    ):
        schema = get_active_dataset_schema(
            role=role
        )

        return any(
            measure.lower() in q
            for measure in schema.measures
        )

    return False


def _extract_horizon_months(
    question: str,
) -> int:
    q = _normalize(
        question
    )

    match = re.search(
        r"\bnext\s+(\d{1,2})\s+months?\b",
        q,
    )

    if match:
        return max(
            1,
            min(
                int(
                    match.group(1)
                ),
                12,
            ),
        )

    match = re.search(
        r"\b(\d{1,2})\s*-\s*month\b",
        q,
    )

    if match:
        return max(
            1,
            min(
                int(
                    match.group(1)
                ),
                12,
            ),
        )

    if (
        "next month"
        in q
        or "upcoming month"
        in q
    ):
        return 1

    if (
        "next quarter"
        in q
        or "upcoming quarter"
        in q
    ):
        return 3

    if (
        "next year"
        in q
        or "upcoming year"
        in q
    ):
        return 12

    return 3


def _extract_measure(
    *,
    question: str,
    role: str,
) -> str | None:
    schema = get_active_dataset_schema(
        role=role
    )

    q = _normalize(
        question
    )

    # Prefer longest matching measure names first so that a specific
    # measure wins over a shorter substring.
    ordered = sorted(
        schema.measures,
        key=len,
        reverse=True,
    )

    for measure in ordered:
        normalized_measure = (
            measure
            .replace(
                "_",
                " ",
            )
            .lower()
        )

        if (
            measure.lower()
            in q
            or normalized_measure
            in q
        ):
            return measure

    return None


def _forecast_rows(
    result: ForecastResult,
) -> list[
    dict[str, Any]
]:
    return [
        {
            "group_name": (
                point.period[:7]
            ),
            "value": point.forecast,
            "forecast": point.forecast,
            "lower_95": point.lower_95,
            "upper_95": point.upper_95,
        }
        for point
        in result.forecast
    ]


def _deterministic_summary(
    result: ForecastResult,
) -> str:
    first = result.forecast[0]
    confidence = (
        result.diagnostics.confidence
    )

    if result.horizon_months == 1:
        return (
            f"The forecast for {result.measure} in {first.period[:7]} "
            f"is {first.forecast:,.2f}, with a 95% range of "
            f"{first.lower_95:,.2f} to {first.upper_95:,.2f}. "
            f"Forecast confidence is {confidence}."
        )

    last = result.forecast[-1]

    return (
        f"The forecast for {result.measure} starts at "
        f"{first.forecast:,.2f} in {first.period[:7]} and reaches "
        f"{last.forecast:,.2f} in {last.period[:7]}. "
        f"Forecast confidence is {confidence}; the 95% ranges "
        "should be treated as uncertainty bounds, not guaranteed outcomes."
    )


def _explain_forecast(
    *,
    question: str,
    result: ForecastResult,
    answer_mode: str,
) -> str:
    payload = forecast_to_dict(
        result
    )

    style = (
        "Answer in 3 to 5 concise sentences."
        if answer_mode
        == "summary"
        else (
            "Give a detailed but focused explanation. Cover the projected "
            "values, uncertainty range, historical trend, back-test quality, "
            "confidence, and the important warnings."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining a deterministic business forecast.

The forecast numbers were already calculated by Bundle's forecasting engine.
You MUST NOT recalculate, change, round into materially different values, or
invent any forecast number.

Rules:
1. Use only the supplied forecast evidence.
2. State future values as forecasts/projections, never guaranteed facts.
3. Mention the 95% interval when discussing a specific future value.
4. Explain the confidence label cautiously.
5. If confidence is low, say why using the supplied diagnostics/warnings.
6. Do not claim causation from a trend forecast.
7. Do not recommend an investment or business action in this forecasting
   response. Decision recommendations require the later decision engine.
8. If history is limited, explicitly say that this limits reliability.
9. Do not imply that R² or confidence is a probability of the forecast being
   correct.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

DETERMINISTIC FORECAST EVIDENCE

{json.dumps(payload, ensure_ascii=False, indent=2)}
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
        # The numerical forecast is already available and valid.
        # A Groq explanation failure must not destroy the forecast result.
        pass

    return _deterministic_summary(
        result
    )


def process_forecast_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    measure = _extract_measure(
        question=question,
        role=role,
    )

    horizon = (
        _extract_horizon_months(
            question
        )
    )

    result = forecast_monthly_measure(
        role=role,
        measure=measure,
        date_column=None,
        horizon_months=horizon,
        lookback_months=24,
    )

    answer = _explain_forecast(
        question=question,
        result=result,
        answer_mode=answer_mode,
    )

    evidence = forecast_to_dict(
        result
    )

    return {
        "answer": answer,
        "rows": _forecast_rows(
            result
        ),
        "group_by": "month",
        "metric": result.measure,
        "source": "forecast",
        "tool_name": "forecast_engine",
        "answer_mode": answer_mode,
        "evidence": evidence,
        "forecast": evidence,
    }

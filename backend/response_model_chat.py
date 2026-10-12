from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dataset_analytics import (
    get_category_value_matches,
)
from backend.response_models import (
    estimate_response,
    list_response_models,
    response_estimate_to_dict,
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


RESPONSE_MODEL_MARKERS = (
    "validated model",
    "response model",
    "model estimate",
    "model estimates",
    "estimated impact",
    "estimate the impact",
    "what impact",
    "what sales impact",
    "expected impact",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def _variable_phrases(
    variable: str,
) -> set[str]:
    normalized = variable.strip().lower()

    phrases = {
        normalized,
        normalized.replace(
            "_",
            " ",
        ),
        normalized.replace(
            "-",
            " ",
        ),
    }

    return {
        " ".join(
            phrase.split()
        )
        for phrase in phrases
        if phrase
    }


def should_use_response_model(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    if any(
        marker in q
        for marker in RESPONSE_MODEL_MARKERS
    ):
        return True

    # Conservative intent fallback. This deliberately requires model language
    # so generic what-if questions continue to use the normal scenario engine.
    return (
        "model" in q
        and (
            "increase" in q
            or "decrease" in q
            or "change" in q
            or "impact" in q
            or "effect" in q
        )
        and (
            "%" in q
            or "percent" in q
        )
    )


def _extract_signed_percent(
    question: str,
) -> float | None:
    q = _normalize(
        question
    )

    patterns = [
        (
            r"\b(increase|increases|increased|rise|rises|grow|grows|growth)"
            r"\b.{0,30}?"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
        ),
        (
            r"\b(decrease|decreases|decreased|drop|drops|decline|declines|fall|falls)"
            r"\b.{0,30}?"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
        ),
        (
            r"([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b)"
            r".{0,20}?"
            r"\b(increase|growth|uplift|decrease|drop|decline)\b"
        ),
    ]

    for index, pattern in enumerate(
        patterns
    ):
        match = re.search(
            pattern,
            q,
        )

        if not match:
            continue

        if index < 2:
            direction = match.group(1)
            value = float(
                match.group(2)
            )
        else:
            value = float(
                match.group(1)
            )
            direction = match.group(2)

        if direction in {
            "decrease",
            "decreases",
            "decreased",
            "drop",
            "drops",
            "decline",
            "declines",
            "fall",
            "falls",
        }:
            return -abs(
                value
            )

        return float(
            value
        )

    explicit = re.search(
        r"([-+]\d+(?:\.\d+)?)\s*(?:%|percent\b)",
        q,
    )

    if explicit:
        return float(
            explicit.group(1)
        )

    return None


def _detect_relationship(
    question: str,
) -> tuple[
    str | None,
    str | None,
    list[dict[str, Any]],
]:
    q = _normalize(
        question
    )

    models = list_response_models(
        validation_status="validated",
    )

    pairs: dict[
        tuple[str, str],
        list[Any],
    ] = {}

    for model in models:
        input_present = any(
            phrase in q
            for phrase in _variable_phrases(
                model.input_variable
            )
        )

        output_present = any(
            phrase in q
            for phrase in _variable_phrases(
                model.output_variable
            )
        )

        if not (
            input_present
            and output_present
        ):
            continue

        key = (
            model.input_variable,
            model.output_variable,
        )

        pairs.setdefault(
            key,
            [],
        ).append(
            model
        )

    if len(
        pairs
    ) != 1:
        candidates = [
            {
                "input_variable": key[0],
                "output_variable": key[1],
                "model_count": len(
                    values
                ),
            }
            for key, values in pairs.items()
        ]

        return (
            None,
            None,
            candidates,
        )

    input_variable, output_variable = next(
        iter(
            pairs.keys()
        )
    )

    return (
        input_variable,
        output_variable,
        [],
    )


def _extract_scope(
    *,
    question: str,
    role: str,
) -> tuple[
    str | None,
    str | None,
]:
    matches = get_category_value_matches(
        question,
        role=role,
    )

    priority = (
        "region",
        "country",
        "product",
        "segment",
        "department",
        "channel",
        "category",
    )

    for column in priority:
        values = matches.get(
            column
        )

        if (
            values
            and len(
                values
            ) == 1
        ):
            return (
                column,
                values[0],
            )

    singles = [
        (
            column,
            values[0],
        )
        for column, values
        in matches.items()
        if len(
            values
        ) == 1
    ]

    if len(
        singles
    ) == 1:
        return singles[0]

    return (
        None,
        None,
    )


def _requirements(
    *,
    question: str,
    missing: list[str],
    answer_mode: str,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "answer": (
            "**Response-model estimate needs clearer explicit inputs.** "
            "I will not guess the relationship or change amount. Please provide: "
            + ", ".join(
                missing
            )
            + "."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "response_model",
        "tool_name": (
            "response_model_requirements"
        ),
        "answer_mode": answer_mode,
        "response_model": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
            "candidate_relationships": (
                candidates
                or []
            ),
        },
    }


def _unavailable(
    *,
    question: str,
    message: str,
    input_variable: str,
    output_variable: str,
    input_change_percent: float,
    scope_type: str | None,
    scope_value: str | None,
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**No validated response model is available for this request.** "
            f"{message} Bundle will not invent the effect. "
            "Use an explicit what-if assumption instead, or have an Admin "
            "register and validate an appropriate response model."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "response_model",
        "tool_name": (
            "response_model_unavailable"
        ),
        "answer_mode": answer_mode,
        "response_model": {
            "supported": False,
            "input_variable": input_variable,
            "output_variable": output_variable,
            "input_change_percent": (
                input_change_percent
            ),
            "scope_type": scope_type,
            "scope_value": scope_value,
            "reason": message,
        },
    }


def _fallback_answer(
    payload: dict[str, Any],
) -> str:
    scope_text = ""

    if (
        payload.get(
            "scope_type"
        )
        and payload.get(
            "scope_value"
        )
    ):
        scope_text = (
            f" for {payload['scope_type']}={payload['scope_value']}"
        )

    return (
        f"Using the registered validated response model "
        f"**{payload['model_name']} v{payload['version']}**{scope_text}, "
        f"a {payload['input_change_percent']:.2f}% change in "
        f"{payload['input_variable']} corresponds to an estimated "
        f"{payload['estimated_output_change_percent']:.2f}% change in "
        f"{payload['output_variable']}. Model confidence is "
        f"{payload['confidence_level']}. This estimate comes from the registered "
        "response model, not from the LLM, and it should not be interpreted as "
        "proof of causality unless the underlying validation supports that claim."
    )


def _explain(
    *,
    question: str,
    payload: dict[str, Any],
    answer_mode: str,
) -> str:
    style = (
        "Give a concise executive explanation in 5 to 7 sentences."
        if answer_mode
        == "summary"
        else (
            "Give a detailed explanation with sections for Requested Change, "
            "Resolved Model, Estimated Response, Validation Evidence, "
            "Confidence / Scope, Causality Boundary, and Bottom Line."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining a deterministic response-model estimate.

Rules:
1. Use all supplied numbers exactly.
2. Never alter or recalculate the estimated response.
3. State clearly that the estimate comes from a registered validated response
   model, not from the LLM.
4. State the model name, version, scope, confidence, and validation metadata
   when available.
5. Do not claim causal certainty merely because validation_status is validated.
6. Distinguish a model estimate from an observed business result.
7. Do not invent ROI, profit impact, revenue amount, or other downstream
   consequences unless they are explicitly present in the result.
8. Mention that extrapolation beyond the model's training range may be unsafe.
9. Do not automatically recommend an operational action.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

VALIDATED RESPONSE-MODEL RESULT

{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}
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
        payload
    )


def process_response_model_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    (
        input_variable,
        output_variable,
        candidates,
    ) = _detect_relationship(
        question
    )

    input_change_percent = (
        _extract_signed_percent(
            question
        )
    )

    scope_type, scope_value = (
        _extract_scope(
            question=question,
            role=role,
        )
    )

    missing: list[str] = []

    if (
        input_variable is None
        or output_variable is None
    ):
        missing.append(
            "one unambiguous registered input → output relationship"
        )

    if input_change_percent is None:
        missing.append(
            "explicit input change percentage"
        )

    if missing:
        return _requirements(
            question=question,
            missing=missing,
            answer_mode=answer_mode,
            candidates=candidates,
        )

    try:
        estimate = estimate_response(
            input_variable=input_variable,
            output_variable=output_variable,
            input_change_percent=(
                input_change_percent
            ),
            scope_type=scope_type,
            scope_value=scope_value,
        )

    except ValueError as exc:
        return _unavailable(
            question=question,
            message=str(
                exc
            ),
            input_variable=input_variable,
            output_variable=output_variable,
            input_change_percent=(
                input_change_percent
            ),
            scope_type=scope_type,
            scope_value=scope_value,
            answer_mode=answer_mode,
        )

    payload = response_estimate_to_dict(
        estimate
    )

    rows = [
        {
            "group_name": (
                f"{estimate.input_variable} change %"
            ),
            "value": (
                estimate.input_change_percent
            ),
        },
        {
            "group_name": (
                f"{estimate.output_variable} estimated change %"
            ),
            "value": (
                estimate.estimated_output_change_percent
            ),
        },
        {
            "group_name": (
                "Model coefficient"
            ),
            "value": (
                estimate.coefficient
            ),
        },
    ]

    return {
        "answer": _explain(
            question=question,
            payload=payload,
            answer_mode=answer_mode,
        ),
        "rows": rows,
        "group_by": (
            "response_model"
        ),
        "metric": "percent",
        "source": (
            "response_model"
        ),
        "tool_name": (
            "response_models"
        ),
        "answer_mode": answer_mode,
        "response_model": payload,
        "evidence": payload,
    }

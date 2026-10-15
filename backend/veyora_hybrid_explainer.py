from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.veyora_hybrid_evidence import (
    build_hybrid_evidence,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=False,
)
load_dotenv(
    BASE_DIR / ".env",
    override=False,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

FORBIDDEN_CAUSAL_PATTERNS = (
    r"\bbecause\b",
    r"\bcaused\b",
    r"\bcauses\b",
    r"\bcausing\b",
    r"\bdue to\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
)

FORBIDDEN_AUTONOMOUS_PATTERNS = (
    r"\bautomatically\b",
    r"\bimmediately implement\b",
    r"\bmust implement\b",
    r"\bmust change\b",
)


def _client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing from the project environment."
        )

    return Groq(
        api_key=GROQ_API_KEY.strip(),
        timeout=30.0,
    )


def _structured_fact_sentence(
    evidence: dict[str, Any],
) -> str:
    structured = evidence.get(
        "structured_evidence",
        {},
    )

    operation = structured.get(
        "operation"
    )

    if operation == "group_ranking":
        rows = structured.get(
            "rows",
            [],
        )

        metric = structured.get(
            "metric"
        )

        group_by = structured.get(
            "group_by"
        )

        if (
            rows
            and metric == "downtime_hours"
            and group_by == "region"
        ):
            top_region = rows[0].get(
                "group_name"
            )

            if top_region:
                return (
                    "Structured data ranks "
                    f"{top_region} as the region "
                    "with the highest average downtime."
                )

        return (
            "Structured data establishes the ranking "
            "used for this analysis."
        )

    if operation == "sla_miss_rate":
        return (
            "Structured data confirms that SLA misses "
            "are present in the dataset."
        )

    return (
        "Structured data does not provide a dedicated "
        "ranking for this question, so the response "
        "uses retrieved operational observations as "
        "context only."
    )


def _safe_evidence_for_llm(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    structured = evidence.get(
        "structured_evidence",
        {},
    )

    rag_rows = evidence.get(
        "rag_evidence",
        [],
    )

    return {
        "question": evidence.get(
            "question"
        ),
        "structured_fact": (
            _structured_fact_sentence(
                evidence
            )
        ),
        "structured_evidence": (
            structured
        ),
        "rag_evidence": [
            {
                "title": row.get(
                    "title"
                ),
                "body": row.get(
                    "body"
                ),
                "similarity": row.get(
                    "similarity"
                ),
            }
            for row in rag_rows
        ],
        "guardrails": evidence.get(
            "guardrails",
            {},
        ),
        "interpretation_rule": (
            evidence.get(
                "interpretation_rule"
            )
        ),
    }


def _extract_structured_top_region(
    evidence: dict[str, Any],
) -> str | None:
    structured = evidence.get(
        "structured_evidence",
        {},
    )

    if (
        structured.get("operation")
        != "group_ranking"
    ):
        return None

    if (
        structured.get("metric")
        != "downtime_hours"
    ):
        return None

    if (
        structured.get("group_by")
        != "region"
    ):
        return None

    rows = structured.get(
        "rows",
        [],
    )

    if not rows:
        return None

    value = rows[0].get(
        "group_name"
    )

    return (
        str(value)
        if value
        else None
    )


def _validate_explanation(
    text: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []

    if re.search(
        r"\d",
        text,
    ):
        problems.append(
            "The qualitative explanation contained numeric characters."
        )

    lowered = text.lower()

    for pattern in (
        FORBIDDEN_CAUSAL_PATTERNS
    ):
        if re.search(
            pattern,
            lowered,
        ):
            problems.append(
                "The explanation used unsupported causal language."
            )
            break

    for pattern in (
        FORBIDDEN_AUTONOMOUS_PATTERNS
    ):
        if re.search(
            pattern,
            lowered,
        ):
            problems.append(
                "The explanation used autonomous action language."
            )
            break

    if evidence:
        top_region = (
            _extract_structured_top_region(
                evidence
            )
        )

        if (
            top_region
            and top_region.lower()
            not in lowered
        ):
            problems.append(
                "The explanation omitted the structured top-region fact."
            )

    return problems


def _extract_unique_manager_notes(
    evidence: dict[str, Any],
    *,
    limit: int = 3,
) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()

    for row in evidence.get(
        "rag_evidence",
        [],
    ):
        body = str(
            row.get(
                "body",
                "",
            )
        )

        match = re.search(
            r"Manager note:\s*(.+?)(?:\n|$)",
            body,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        sentence = (
            match.group(1)
            .strip()
        )

        normalized = re.sub(
            r"\s+",
            " ",
            sentence.lower(),
        )

        if (
            not sentence
            or normalized in seen
        ):
            continue

        seen.add(
            normalized
        )

        notes.append(
            sentence
        )

        if len(notes) >= limit:
            break

    return notes


def _fallback_explanation(
    evidence: dict[str, Any],
) -> str:
    structured_fact = (
        _structured_fact_sentence(
            evidence
        )
    )

    notes = (
        _extract_unique_manager_notes(
            evidence,
            limit=3,
        )
    )

    if notes:
        note_text = " ".join(
            notes
        )

        return (
            f"{structured_fact} "
            "Retrieved operational notes include the following "
            f"related observations: {note_text} "
            "These observations are contextual associations only. "
            "They do not change the structured ranking and do not "
            "prove causation."
        )

    return (
        f"{structured_fact} "
        "No sufficiently relevant operational note evidence was "
        "available for a stronger contextual explanation. "
        "The available evidence does not establish causation."
    )


def explain_hybrid_evidence(
    question: str,
    *,
    dataset_name: str = "veyora_massive",
    role: str = "analyst",
) -> dict[str, Any]:
    evidence = build_hybrid_evidence(
        question,
        dataset_name=dataset_name,
        role=role,
    )

    llm_input = (
        _safe_evidence_for_llm(
            evidence
        )
    )

    system_prompt = """
You are Bundle Data Assistant's grounded explanation layer.

You receive an already-validated evidence package.

Rules:
- Start with the exact structured_fact provided in the evidence package.
- Treat structured SQL evidence as authoritative for rankings and metrics.
- Retrieved RAG notes are contextual observations only.
- A region mentioned inside a retrieved note must never override or contradict
  the structured ranking.
- If retrieved notes mention a different region from the structured top region,
  clearly describe those as note context only, not as the ranked result.
- Do not calculate anything.
- Do not introduce any new facts.
- Do not write any digits or numeric values in the explanation.
- Do not claim that an operational note caused a metric.
- Use wording such as "associated with", "appears in the retrieved notes",
  "related observation", or "may warrant investigation".
- Do not recommend autonomous business actions.
- Keep the explanation concise and useful.
- PostgreSQL is the source of numeric truth.
- RAG evidence must never override SQL facts.

Return only the explanation text.
""".strip()

    user_prompt = (
        "Original question:\n"
        + question
        + "\n\nValidated evidence package:\n"
        + json.dumps(
            llm_input,
            ensure_ascii=False,
            default=str,
        )
    )

    response = (
        _client()
        .chat
        .completions
        .create(
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
    )

    explanation = (
        response
        .choices[0]
        .message
        .content
        or ""
    ).strip()

    validation_problems = (
        _validate_explanation(
            explanation,
            evidence=evidence,
        )
    )

    used_fallback = False

    if (
        not explanation
        or validation_problems
    ):
        explanation = (
            _fallback_explanation(
                evidence
            )
        )
        used_fallback = True

    return {
        "source": (
            "veyora_grounded_hybrid_explanation"
        ),
        "dataset_name": dataset_name,
        "role": role,
        "question": question,
        "answer": explanation,
        "evidence": evidence,
        "explanation_guardrails": {
            "llm_provider": "Groq",
            "model": GROQ_MODEL,
            "llm_calculates_numbers": False,
            "numeric_truth_source": "PostgreSQL",
            "rag_context_only": True,
            "structured_fact_precedence": True,
            "cross_region_rag_cannot_override_sql": True,
            "causal_claim_allowed": False,
            "numeric_text_allowed_in_llm_explanation": False,
            "validation_passed": (
                not validation_problems
            ),
            "fallback_used": used_fallback,
            "validation_problems": (
                validation_problems
            ),
        },
    }


def main() -> None:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "question"
    )

    parser.add_argument(
        "--dataset-name",
        default="veyora_massive",
    )

    parser.add_argument(
        "--role",
        default="analyst",
        choices=[
            "admin",
            "analyst",
            "viewer",
        ],
    )

    args = parser.parse_args()

    result = (
        explain_hybrid_evidence(
            args.question,
            dataset_name=(
                args.dataset_name
            ),
            role=args.role,
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

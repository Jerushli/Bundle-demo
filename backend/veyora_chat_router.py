from __future__ import annotations

import re
from typing import Any

from backend.veyora_hybrid_explainer import explain_hybrid_evidence


_ALLOWED_ROLES = {"admin", "analyst"}

_REGION_WORDS = (
    "north",
    "south",
    "east",
    "west",
)

_OPERATIONAL_TERMS = (
    "downtime",
    "sla",
    "workshop",
    "supplier",
    "component shortage",
    "parts shortage",
    "service delay",
    "maintenance delay",
    "operational",
    "operations",
)

_EXPLANATION_TERMS = (
    "why",
    "reason",
    "reasons",
    "happening",
    "happen",
    "issue",
    "issues",
    "problem",
    "problems",
    "investigate",
    "associated",
    "association",
    "related",
    "relationship",
    "linked",
)


def should_route_veyora_hybrid(
    question: str,
) -> bool:
    text = question.strip().lower()

    if not text:
        return False

    explicit_veyora = (
        "veyora" in text
    )

    has_operational_term = any(
        term in text
        for term in _OPERATIONAL_TERMS
    )

    has_explanation_intent = any(
        re.search(
            rf"\b{re.escape(term)}\b",
            text,
        )
        for term in _EXPLANATION_TERMS
    )

    has_region = any(
        re.search(
            rf"\b{region}\b",
            text,
        )
        for region in _REGION_WORDS
    )

    # Explicit Veyora operational/investigation questions.
    if (
        explicit_veyora
        and (
            has_operational_term
            or has_explanation_intent
        )
    ):
        return True

    # Hybrid operational explanation / association questions.
    if (
        has_operational_term
        and has_explanation_intent
    ):
        return True

    # Direct supplier/SLA association phrasing.
    if (
        "supplier" in text
        and "sla" in text
    ):
        return True

    # Narrow regional downtime path.
    if (
        has_region
        and "downtime" in text
    ):
        return True

    return False


def maybe_process_veyora_chat(
    question: str,
    *,
    role: str,
) -> dict[str, Any] | None:
    if role not in _ALLOWED_ROLES:
        return None

    if not should_route_veyora_hybrid(
        question
    ):
        return None

    result = explain_hybrid_evidence(
        question,
        dataset_name="veyora_massive",
        role=role,
    )

    result["tool_name"] = (
        "veyora_hybrid_intelligence"
    )

    result["chat_route"] = (
        "veyora_hybrid"
    )

    return result

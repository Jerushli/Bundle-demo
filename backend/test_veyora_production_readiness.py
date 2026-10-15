from __future__ import annotations

import re

from backend.veyora_chat_router import (
    maybe_process_veyora_chat,
)
from backend.veyora_hybrid_explainer import (
    explain_hybrid_evidence,
)


VEYORA_CASES = [
    {
        "name": "north_downtime",
        "question": "Why is North showing higher downtime?",
        "expected_operation": "group_ranking",
    },
    {
        "name": "sla_failures",
        "question": "Why are SLA failures happening?",
        "expected_operation": "sla_miss_rate",
    },
    {
        "name": "supplier_delay",
        "question": "Are supplier delays associated with SLA misses?",
        "expected_operation": "sla_miss_rate",
    },
    {
        "name": "high_downtime_issues",
        "question": "What operational issues appear most often in high-downtime jobs?",
        "expected_operation": "group_ranking",
    },
    {
        "name": "management_priorities",
        "question": "What operational problems should management investigate first in Veyora?",
        "expected_operation": "no_structured_operation_selected",
    },
]


FORBIDDEN_FINAL_PATTERNS = (
    r"\d",
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|million|billion|percent|"
    r"percentage|half|quarter|third|double|triple)\b",
    r"\b(?:miss rate|sla miss rate|rate)\s+(?:is\s+)?"
    r"(?:above|below|over|under)\s+(?:the\s+)?"
    r"(?:target|threshold|benchmark)\b",
)


def _assert_final_answer_safe(
    answer: str,
) -> None:
    assert answer.strip(), "Final answer is empty."

    for pattern in FORBIDDEN_FINAL_PATTERNS:
        assert not re.search(
            pattern,
            answer,
            flags=re.IGNORECASE,
        ), (
            "Final answer contains forbidden numeric or "
            f"unsupported benchmark language: {pattern}"
        )


def _check_case(
    case: dict[str, str],
) -> None:
    question = case["question"]

    routed = maybe_process_veyora_chat(
        question,
        role="analyst",
    )

    assert routed is not None, (
        f"Router failed for {case['name']}."
    )

    result = explain_hybrid_evidence(
        question,
        role="analyst",
    )

    assert (
        result["source"]
        == "veyora_grounded_hybrid_explanation"
    )

    evidence = result["evidence"]
    structured = evidence["structured_evidence"]
    guardrails = evidence["guardrails"]
    explanation_guardrails = (
        result["explanation_guardrails"]
    )

    assert (
        structured["operation"]
        == case["expected_operation"]
    ), (
        f"{case['name']}: unexpected structured operation: "
        f"{structured['operation']}"
    )

    assert (
        guardrails["numeric_truth_source"]
        == "PostgreSQL"
    )
    assert guardrails["rag_role_filtered"] is True
    assert (
        guardrails[
            "rag_region_filtered_when_present"
        ]
        is True
    )
    assert (
        guardrails[
            "rag_minimum_similarity_enforced"
        ]
        is True
    )
    assert (
        guardrails[
            "rag_duplicate_suppression_enforced"
        ]
        is True
    )
    assert guardrails["causality_claimed"] is False
    assert (
        guardrails["autonomous_action_taken"]
        is False
    )

    assert (
        explanation_guardrails[
            "numeric_truth_source"
        ]
        == "PostgreSQL"
    )
    assert (
        explanation_guardrails[
            "rag_context_only"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "structured_fact_precedence"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "cross_region_rag_cannot_override_sql"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "semantic_numeric_leakage_blocked"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "unsupported_benchmark_claims_blocked"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "final_answer_validation_passed"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "validation_passed"
        ]
        is True
    )
    assert (
        explanation_guardrails[
            "final_answer_validation_problems"
        ]
        == []
    )
    assert (
        explanation_guardrails[
            "validation_problems"
        ]
        == []
    )

    _assert_final_answer_safe(
        result["answer"]
    )

    print(
        "[PASS] "
        f"{case['name']} | "
        f"operation={structured['operation']} | "
        f"fallback={explanation_guardrails['fallback_used']}"
    )


def main() -> None:
    print(
        "Veyora Production Readiness Regression"
    )
    print("=" * 65)

    # Non-Veyora question must stay on the normal Bundle path.
    generic = maybe_process_veyora_chat(
        "What is total revenue?",
        role="analyst",
    )

    assert generic is None, (
        "Generic dataset question was incorrectly captured "
        "by the Veyora router."
    )

    print(
        "[PASS] Generic Bundle routing isolation"
    )

    for case in VEYORA_CASES:
        _check_case(case)

    print("=" * 65)
    print(
        "Routing isolation: PASSED"
    )
    print(
        "Structured SQL evidence: PASSED"
    )
    print(
        "Secure RAG guardrails: PASSED"
    )
    print(
        "Groq/fallback validation: PASSED"
    )
    print(
        "Validation metadata correctness: PASSED"
    )
    print(
        "Numeric/benchmark grounding: PASSED"
    )
    print(
        "Veyora production readiness regression: PASSED"
    )


if __name__ == "__main__":
    main()

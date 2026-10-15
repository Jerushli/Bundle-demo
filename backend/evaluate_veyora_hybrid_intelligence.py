from __future__ import annotations

import json
import sys
from typing import Any

from backend.veyora_chat_router import (
    maybe_process_veyora_chat,
    should_route_veyora_hybrid,
)


TEST_CASES = [
    {
        "name": "north_downtime",
        "question": "Why is North showing higher downtime?",
        "expect_route": True,
        "expected_operation": "group_ranking",
        "expected_region": "North",
    },
    {
        "name": "sla_failures",
        "question": "Why are SLA failures happening?",
        "expect_route": True,
        "expected_operation": "sla_miss_rate",
        "expected_region": None,
    },
    {
        "name": "supplier_delay_association",
        "question": "Are supplier delays associated with SLA misses?",
        "expect_route": True,
        "expected_operation": "sla_miss_rate",
        "expected_region": None,
    },
    {
        "name": "high_downtime_issues",
        "question": (
            "What operational issues appear most often "
            "in high-downtime jobs?"
        ),
        "expect_route": True,
        "expected_operation": "group_ranking",
        "expected_region": None,
    },
    {
        "name": "management_priorities",
        "question": (
            "What operational problems should management "
            "investigate first in Veyora?"
        ),
        "expect_route": True,
        "expected_operation": None,
        "expected_region": None,
    },
]


def _get_nested(
    value: dict[str, Any],
    *keys: str,
) -> Any:
    current: Any = value

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def evaluate_case(
    case: dict[str, Any],
) -> dict[str, Any]:
    question = case["question"]

    route_selected = (
        should_route_veyora_hybrid(
            question
        )
    )

    checks: list[
        dict[str, Any]
    ] = []

    checks.append(
        {
            "check": "router_selected",
            "passed": (
                route_selected
                == case["expect_route"]
            ),
            "actual": route_selected,
            "expected": (
                case["expect_route"]
            ),
        }
    )

    if not route_selected:
        return {
            "name": case["name"],
            "question": question,
            "passed": False,
            "checks": checks,
            "result_summary": None,
        }

    result = (
        maybe_process_veyora_chat(
            question,
            role="analyst",
        )
    )

    checks.extend(
        [
            {
                "check": "result_exists",
                "passed": (
                    result is not None
                ),
            },
            {
                "check": "hybrid_source",
                "passed": (
                    result is not None
                    and result.get(
                        "source"
                    )
                    == (
                        "veyora_grounded_"
                        "hybrid_explanation"
                    )
                ),
            },
            {
                "check": "chat_route",
                "passed": (
                    result is not None
                    and result.get(
                        "chat_route"
                    )
                    == "veyora_hybrid"
                ),
            },
            {
                "check": "tool_name",
                "passed": (
                    result is not None
                    and result.get(
                        "tool_name"
                    )
                    == (
                        "veyora_hybrid_"
                        "intelligence"
                    )
                ),
            },
            {
                "check": (
                    "numeric_truth_postgresql"
                ),
                "passed": (
                    _get_nested(
                        result or {},
                        "explanation_guardrails",
                        "numeric_truth_source",
                    )
                    == "PostgreSQL"
                ),
            },
            {
                "check": "rag_context_only",
                "passed": (
                    _get_nested(
                        result or {},
                        "explanation_guardrails",
                        "rag_context_only",
                    )
                    is True
                ),
            },
            {
                "check": "causal_claim_blocked",
                "passed": (
                    _get_nested(
                        result or {},
                        "explanation_guardrails",
                        "causal_claim_allowed",
                    )
                    is False
                ),
            },
            {
                "check": (
                    "autonomous_action_not_taken"
                ),
                "passed": (
                    _get_nested(
                        result or {},
                        "evidence",
                        "guardrails",
                        "autonomous_action_taken",
                    )
                    is False
                ),
            },
        ]
    )

    expected_operation = (
        case.get(
            "expected_operation"
        )
    )

    actual_operation = (
        _get_nested(
            result or {},
            "evidence",
            "structured_evidence",
            "operation",
        )
    )

    if expected_operation is not None:
        checks.append(
            {
                "check": (
                    "structured_operation"
                ),
                "passed": (
                    actual_operation
                    == expected_operation
                ),
                "actual": (
                    actual_operation
                ),
                "expected": (
                    expected_operation
                ),
            }
        )

    expected_region = case.get(
        "expected_region"
    )

    if expected_region is not None:
        actual_region = (
            _get_nested(
                result or {},
                "evidence",
                "rag_retrieval",
                "detected_region",
            )
        )

        checks.append(
            {
                "check": (
                    "region_detection"
                ),
                "passed": (
                    actual_region
                    == expected_region
                ),
                "actual": actual_region,
                "expected": (
                    expected_region
                ),
            }
        )

    answer = (
        str(
            (result or {}).get(
                "answer",
                "",
            )
        )
        .strip()
    )

    checks.append(
        {
            "check": "answer_present",
            "passed": bool(answer),
        }
    )

    failed = [
        item
        for item in checks
        if not item.get(
            "passed",
            False,
        )
    ]

    return {
        "name": case["name"],
        "question": question,
        "passed": not failed,
        "checks": checks,
        "result_summary": {
            "answer": answer,
            "structured_operation": (
                actual_operation
            ),
            "rag_result_count": (
                _get_nested(
                    result or {},
                    "evidence",
                    "rag_retrieval",
                    "result_count",
                )
            ),
            "fallback_used": (
                _get_nested(
                    result or {},
                    "explanation_guardrails",
                    "fallback_used",
                )
            ),
            "validation_passed": (
                _get_nested(
                    result or {},
                    "explanation_guardrails",
                    "validation_passed",
                )
            ),
        },
    }


def main() -> None:
    print(
        "Veyora Hybrid Intelligence Evaluation"
    )
    print("=" * 60)

    results: list[
        dict[str, Any]
    ] = []

    for case in TEST_CASES:
        print()
        print(
            f"[RUN] {case['name']}"
        )
        print(
            case["question"]
        )

        try:
            result = evaluate_case(
                case
            )
        except Exception as exc:
            result = {
                "name": (
                    case["name"]
                ),
                "question": (
                    case["question"]
                ),
                "passed": False,
                "checks": [],
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

        results.append(
            result
        )

        print(
            "PASS"
            if result.get(
                "passed"
            )
            else "FAIL"
        )

        if result.get(
            "error"
        ):
            print(
                "Error:",
                result["error"],
            )

        summary = result.get(
            "result_summary"
        )

        if summary:
            print(
                "Structured operation:",
                summary.get(
                    "structured_operation"
                ),
            )
            print(
                "RAG result count:",
                summary.get(
                    "rag_result_count"
                ),
            )
            print(
                "Fallback used:",
                summary.get(
                    "fallback_used"
                ),
            )

    passed_count = sum(
        1
        for item in results
        if item.get(
            "passed"
        )
    )

    total = len(
        results
    )

    print()
    print("=" * 60)
    print(
        f"Score: {passed_count}/{total}"
    )

    failed_names = [
        item["name"]
        for item in results
        if not item.get(
            "passed"
        )
    ]

    print(
        "Failed cases:",
        failed_names
        if failed_names
        else "none",
    )

    output = {
        "suite": (
            "veyora_hybrid_intelligence"
        ),
        "passed": passed_count,
        "total": total,
        "results": results,
    }

    print()
    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    if passed_count != total:
        sys.exit(1)


if __name__ == "__main__":
    main()

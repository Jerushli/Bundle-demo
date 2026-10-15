from backend.veyora_hybrid_explainer import (
    _fallback_explanation,
    _structured_fact_sentence,
    _validate_explanation,
)


print("Veyora explanation quality hardening test")
print("=" * 55)

sample_evidence = {
    "structured_evidence": {
        "operation": "group_ranking",
        "metric": "downtime_hours",
        "group_by": "region",
        "rows": [
            {
                "group_name": "North",
                "value": 3.94,
            },
            {
                "group_name": "South",
                "value": 3.51,
            },
        ],
    },
    "rag_evidence": [
        {
            "body": (
                "Region: South\n"
                "Manager note: Supplier delays were reported."
            ),
        },
        {
            "body": (
                "Region: South\n"
                "Manager note: Supplier delays were reported."
            ),
        },
        {
            "body": (
                "Region: North\n"
                "Manager note: Workshop congestion was observed."
            ),
        },
    ],
}

fact = _structured_fact_sentence(
    sample_evidence
)

assert (
    fact
    == (
        "Structured data ranks North as the region "
        "with the highest average downtime."
    )
)

safe_text = (
    "Structured data ranks North as the region with the "
    "highest average downtime. Retrieved notes also mention "
    "South as contextual evidence only."
)

assert _validate_explanation(
    safe_text,
    evidence=sample_evidence,
) == []

bad_text = (
    "Retrieved notes mention South as the important region."
)

assert _validate_explanation(
    bad_text,
    evidence=sample_evidence,
)

fallback = (
    _fallback_explanation(
        sample_evidence
    )
)

assert (
    fallback.startswith(
        "Structured data ranks North"
    )
)

assert (
    fallback.count(
        "Supplier delays were reported."
    )
    == 1
)

print("Structured ranking precedence: PASSED")
print("Cross-region context handling: PASSED")
print("Top-region omission blocker: PASSED")
print("Fallback note deduplication: PASSED")
print(
    "Veyora explanation quality hardening test passed."
)

from backend.veyora_hybrid_explainer import (
    _extract_unique_manager_notes,
    _fallback_explanation,
)


print("Veyora fallback answer quality test")
print("=" * 55)

sample = {
    "structured_evidence": {
        "operation": "sla_miss_rate",
    },
    "rag_evidence": [
        {
            "body": (
                "Manager note: The SLA target was missed for this "
                "service event. A supplier delivery delay affected "
                "selected repairs, while routine maintenance "
                "continued without interruption."
            )
        },
        {
            "body": (
                "Manager note: A supplier delivery delay affected "
                "selected repairs, while routine maintenance "
                "continued without interruption."
            )
        },
        {
            "body": (
                "Manager note: Technicians reported intermittent "
                "component shortages and rescheduled a small "
                "number of jobs."
            )
        },
        {
            "body": (
                "Manager note: Workshop congestion increased "
                "waiting time during the afternoon shift."
            )
        },
    ],
}

notes = _extract_unique_manager_notes(
    sample,
    limit=3,
)

assert len(notes) == 3

supplier_mentions = sum(
    1
    for note in notes
    if "supplier delivery delay" in note.lower()
)

assert supplier_mentions == 1

fallback = _fallback_explanation(
    sample
)

assert (
    fallback.lower().count(
        "supplier delivery delay"
    )
    == 1
)

assert (
    "Related observation:"
    in fallback
)

print("Exact duplicate suppression: PASSED")
print("Near-duplicate suppression: PASSED")
print("Supplier-note repetition blocker: PASSED")
print("Clean fallback structure: PASSED")
print("Veyora fallback answer quality test passed.")

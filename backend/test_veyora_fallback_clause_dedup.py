from backend.veyora_hybrid_explainer import (
    _dedupe_clauses_across_notes,
    _fallback_explanation,
)


print("Veyora fallback clause deduplication test")
print("=" * 58)

notes = [
    (
        "An exception was logged: unusually high workshop "
        "time and cost were recorded; operations requested "
        "a manual review of the job. "
        "A supplier delivery delay affected selected repairs."
    ),
    (
        "An exception was logged: unusually high workshop "
        "time and cost were recorded; operations requested "
        "a manual review of the job. "
        "The client requested faster turnaround."
    ),
    (
        "An exception was logged: unusually high workshop "
        "time and cost were recorded; operations requested "
        "a manual review of the job. "
        "Several vehicles required repeat diagnostics."
    ),
]

clauses = _dedupe_clauses_across_notes(
    notes,
    max_clauses=4,
)

shared_count = sum(
    1
    for clause in clauses
    if "unusually high workshop time" in clause.lower()
)

assert shared_count == 1

assert any(
    "supplier delivery delay" in clause.lower()
    for clause in clauses
)

assert any(
    "faster turnaround" in clause.lower()
    for clause in clauses
)

sample_evidence = {
    "structured_evidence": {
        "operation": "no_structured_operation_selected",
    },
    "rag_evidence": [
        {
            "body": (
                "Manager note: "
                + notes[0]
            )
        },
        {
            "body": (
                "Manager note: "
                + notes[1]
            )
        },
        {
            "body": (
                "Manager note: "
                + notes[2]
            )
        },
    ],
}

fallback = _fallback_explanation(
    sample_evidence
)

assert (
    fallback.lower().count(
        "unusually high workshop time"
    )
    == 1
)

print("Shared-clause suppression: PASSED")
print("Distinct observation preservation: PASSED")
print("Fallback repeated-intro blocker: PASSED")
print("Veyora fallback clause deduplication test passed.")

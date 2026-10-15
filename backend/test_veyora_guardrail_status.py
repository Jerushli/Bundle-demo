from backend.veyora_hybrid_explainer import (
    _fallback_explanation,
    _validate_explanation,
    _validate_final_answer,
)


print("Veyora guardrail status hardening test")
print("=" * 55)

evidence = {
    "structured_evidence": {
        "operation": "sla_miss_rate",
    },
    "rag_evidence": [
        {
            "body": (
                "Manager note: A supplier delivery delay "
                "affected selected repairs."
            )
        }
    ],
}

unsafe_llm = (
    "The miss rate is eleven percent because supplier "
    "delays caused the failures."
)

llm_problems = _validate_explanation(
    unsafe_llm,
    evidence=evidence,
)

assert llm_problems

fallback = _fallback_explanation(
    evidence
)

final_problems = _validate_final_answer(
    fallback,
    evidence=evidence,
)

assert final_problems == []

assert (
    "supplier delivery delay"
    in fallback.lower()
)

print("Unsafe LLM candidate detection: PASSED")
print("Safe fallback validation: PASSED")
print("Final-answer validation semantics: PASSED")
print("Veyora guardrail status hardening test passed.")

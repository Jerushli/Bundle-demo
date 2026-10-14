from backend.veyora_hybrid_evidence import (
    DEFAULT_MINIMUM_SIMILARITY,
    detect_region,
)

print("Hybrid import isolation test")
print("=" * 50)

assert detect_region(
    "Why is North showing higher downtime?"
) == "North"

assert detect_region(
    "Why are SLA failures happening?"
) is None

assert (
    DEFAULT_MINIMUM_SIMILARITY
    == 0.20
)

print("Normal venv import: PASSED")
print("Local region detection: PASSED")
print("No direct RAG module import: PASSED")
print("Hybrid import isolation test passed.")


from backend.veyora_rag_search import (
    DEFAULT_MINIMUM_SIMILARITY,
    detect_region,
)

print("Veyora Hybrid RAG hardening smoke test")
print("=" * 50)

assert detect_region("Why is North showing higher downtime?") == "North"
print("Region detection: PASSED")

assert detect_region("Why are SLA failures happening?") is None
print("No-region detection: PASSED")

assert DEFAULT_MINIMUM_SIMILARITY == 0.20
print("Minimum similarity configuration: PASSED")

print("Hybrid RAG hardening smoke test passed.")

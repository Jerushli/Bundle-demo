from backend.veyora_chat_router import (
    should_route_veyora_hybrid,
)

print("Veyora real-chat routing smoke test")
print("=" * 50)

assert should_route_veyora_hybrid(
    "Why is North showing higher downtime?"
)

assert should_route_veyora_hybrid(
    "Why are SLA failures happening?"
)

assert should_route_veyora_hybrid(
    "What operational issues should we investigate in Veyora?"
)

assert not should_route_veyora_hybrid(
    "What is total revenue?"
)

assert not should_route_veyora_hybrid(
    "Show profit by country"
)

assert not should_route_veyora_hybrid(
    "Compare Germany with France"
)

print("North downtime route: PASSED")
print("SLA route: PASSED")
print("Explicit Veyora route: PASSED")
print("Existing financial chat bypass: PASSED")
print("Veyora real-chat routing smoke test passed.")

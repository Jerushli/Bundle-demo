from backend.veyora_chat_router import (
    should_route_veyora_hybrid,
)

print("Veyora chat routing regression test")
print("=" * 52)

positive_cases = [
    "Why is North showing higher downtime?",
    "Why are SLA failures happening?",
    "What operational issues should we investigate in Veyora?",
    "Are supplier delays associated with SLA misses?",
    "Is supplier delay related to SLA misses?",
]

negative_cases = [
    "What is total revenue?",
    "Show profit by country",
    "Compare Germany with France",
]

for question in positive_cases:
    assert should_route_veyora_hybrid(
        question
    ), question

for question in negative_cases:
    assert not should_route_veyora_hybrid(
        question
    ), question

print("North downtime route: PASSED")
print("SLA route: PASSED")
print("Explicit Veyora route: PASSED")
print("Supplier/SLA association route: PASSED")
print("Existing financial chat bypass: PASSED")
print("Veyora chat routing regression test passed.")

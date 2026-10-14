from backend.veyora_hybrid_explainer import (
    _validate_explanation,
)

print("Veyora grounded Groq explanation validator test")
print("=" * 55)

safe = (
    "North has the strongest observed downtime pattern. "
    "Retrieved operational notes mention workshop congestion "
    "and component shortages as related observations. "
    "These associations may warrant investigation."
)

assert _validate_explanation(
    safe
) == []

assert _validate_explanation(
    "North downtime is 3.94 hours."
)

assert _validate_explanation(
    "This happened because workshop congestion increased."
)

assert _validate_explanation(
    "Management must implement this immediately."
)

print("Safe qualitative explanation: PASSED")
print("Numeric hallucination blocker: PASSED")
print("Causal language blocker: PASSED")
print("Autonomous action blocker: PASSED")
print("Grounded explanation validator test passed.")

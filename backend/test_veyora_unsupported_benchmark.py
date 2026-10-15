from backend.veyora_hybrid_explainer import (
    _validate_explanation,
)


print("Veyora unsupported benchmark hardening test")
print("=" * 58)

safe = (
    "Structured data confirms that SLA misses are present "
    "in the dataset. Retrieved notes contain related "
    "operational observations."
)

assert _validate_explanation(safe) == []

bad_cases = [
    "The miss rate is above the target.",
    "The SLA miss rate is below the threshold.",
    "The rate is over the benchmark.",
    "The miss rate is higher than the target.",
    "The rate falls below the benchmark.",
]

for text in bad_cases:
    problems = _validate_explanation(text)
    assert any(
        "unsupported benchmark" in problem
        for problem in problems
    ), text

allowed_note_context = (
    "A retrieved note states that the SLA target was missed "
    "for the service event."
)

# Mentioning an SLA target from a note is not the same as inventing a
# quantitative comparison between the aggregate miss rate and a benchmark.
assert _validate_explanation(
    allowed_note_context
) == []

print("Unsupported target comparison blocker: PASSED")
print("Unsupported threshold comparison blocker: PASSED")
print("Unsupported benchmark comparison blocker: PASSED")
print("Legitimate note wording preserved: PASSED")
print("Veyora unsupported benchmark hardening test passed.")

from backend.veyora_hybrid_explainer import (
    _validate_explanation,
)


print("Veyora semantic numeric leakage test")
print("=" * 55)

safe = (
    "Structured data confirms that SLA misses are present "
    "in the dataset. Retrieved notes mention supplier delays "
    "as related operational context."
)

assert _validate_explanation(
    safe
) == []

digit_leak = (
    "The miss rate is 11 percent."
)

assert _validate_explanation(
    digit_leak
)

word_leak = (
    "The miss rate is roughly eleven percent."
)

problems = _validate_explanation(
    word_leak
)

assert any(
    "number words" in problem
    for problem in problems
)

fraction_leak = (
    "About half of the events show this pattern."
)

assert _validate_explanation(
    fraction_leak
)

vague_quantifier = (
    "Several retrieved notes mention supplier delays."
)

assert _validate_explanation(
    vague_quantifier
) == []

print("Digit numeric leakage blocker: PASSED")
print("Number-word leakage blocker: PASSED")
print("Fraction-word leakage blocker: PASSED")
print("Vague qualitative wording allowed: PASSED")
print(
    "Veyora semantic numeric leakage test passed."
)

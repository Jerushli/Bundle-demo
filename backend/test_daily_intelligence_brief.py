from __future__ import annotations

from backend.daily_intelligence_brief import (
    _fallback_executive_summary,
    _validate_llm_summary,
    build_deterministic_fact_markdown,
)
from backend.daily_intelligence_evidence import (
    build_daily_evidence_package,
)


def main() -> None:
    print("Stage 21.4 smoke test")
    print("=" * 50)

    evidence = build_daily_evidence_package(
        role="admin",
        persist=False,
    )

    markdown = build_deterministic_fact_markdown(
        evidence
    )

    assert "Daily Intelligence Facts" in markdown
    assert "KPI Snapshot" in markdown
    assert "Change Detection" in markdown
    assert "Response-Model Governance" in markdown

    valid, reason = _validate_llm_summary(
        "The latest evidence is stable under the configured monitoring rules."
    )

    assert valid is True
    assert reason is None

    valid, reason = _validate_llm_summary(
        "Sales increased by 12 percent."
    )

    assert valid is False
    assert reason == "numeric_content_not_allowed"

    valid, reason = _validate_llm_summary(
        "Performance improved because marketing activity increased."
    )

    assert valid is False
    assert reason == "unsupported_causal_language"

    fallback = _fallback_executive_summary(
        evidence
    )

    assert fallback

    print(
        "Dataset:",
        evidence["dataset"]["dataset_name"],
    )

    print(
        "Deterministic fact renderer: PASSED"
    )

    print(
        "LLM numeric guardrail: PASSED"
    )

    print(
        "LLM causal guardrail: PASSED"
    )

    print(
        "Fallback summary: PASSED"
    )

    print(
        "Stage 21.4 smoke test passed."
    )


if __name__ == "__main__":
    main()

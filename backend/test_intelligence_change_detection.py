from __future__ import annotations

from decimal import Decimal

from backend.intelligence_change_detection import (
    classify_percentage_change,
    detect_latest_changes,
    list_change_rules,
)


def _assert_unit_classification() -> None:
    normal = classify_percentage_change(
        Decimal("4"),
        warning_change_percent=Decimal("10"),
        critical_change_percent=Decimal("25"),
    )
    assert normal["severity"] == "normal"

    warning = classify_percentage_change(
        Decimal("-12"),
        warning_change_percent=Decimal("10"),
        critical_change_percent=Decimal("25"),
    )
    assert warning["severity"] == "warning"

    critical = classify_percentage_change(
        Decimal("30"),
        warning_change_percent=Decimal("10"),
        critical_change_percent=Decimal("25"),
    )
    assert critical["severity"] == "critical"

    no_rule = classify_percentage_change(
        Decimal("50"),
        warning_change_percent=None,
        critical_change_percent=None,
    )
    assert no_rule["severity"] == "unclassified"

    zero_baseline = classify_percentage_change(
        None,
        warning_change_percent=Decimal("10"),
        critical_change_percent=Decimal("25"),
    )
    assert zero_baseline["severity"] == "unclassified"


def main() -> None:
    print("Stage 21.2 smoke test")
    print("=" * 50)

    _assert_unit_classification()

    print("Deterministic classification tests: PASSED")

    rules = list_change_rules(
        include_disabled=True
    )

    print(
        "Configured change rules:",
        len(rules["rules"]),
    )

    result = detect_latest_changes(
        persist=False
    )

    print(
        "Evaluated KPIs:",
        len(result["changes"]),
    )

    print(
        "Severity counts:",
        result["severity_counts"],
    )

    print("Stage 21.2 smoke test passed.")


if __name__ == "__main__":
    main()

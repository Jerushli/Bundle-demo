from __future__ import annotations

from backend.structured_analytics_router import (
    normalize_dataset_name,
    prepare_structured_rows,
)


def main() -> None:
    print(
        "Stage 22.6 smoke test"
    )

    print(
        "=" * 50
    )

    review_result = {
        "records": [
            {
                "source_row_number": 1,
                "source_column": "data",
                "routing_status": "eligible_for_routing",
                "normalized_fields": {
                    "date": "2026-10-01",
                    "sales": 250000.0,
                    "region": "South India",
                },
            },
            {
                "source_row_number": 2,
                "source_column": "data",
                "routing_status": "needs_human_review",
                "normalized_fields": {
                    "date": "2026-10-02",
                    "sales": 180000.0,
                    "region": "North India",
                    "custom_code": "ABC",
                },
            },
            {
                "source_row_number": 3,
                "source_column": "data",
                "routing_status": "blocked",
                "normalized_fields": {},
            },
        ]
    }

    decisions = {
        (
            2,
            "data",
        ): "approved",
    }

    prepared = prepare_structured_rows(
        review_result,
        review_decisions=decisions,
    )

    assert (
        prepared[
            "routed_count"
        ]
        == 2
    )

    assert (
        prepared[
            "blocked_count"
        ]
        == 1
    )

    assert (
        prepared[
            "column_types"
        ][
            "sales"
        ]
        == "NUMERIC"
    )

    assert (
        prepared[
            "column_types"
        ][
            "date"
        ]
        == "DATE"
    )

    assert (
        normalize_dataset_name(
            "Demo Embedded Sales"
        )
        == "demo_embedded_sales"
    )

    print(
        "High-confidence routing: PASSED"
    )

    print(
        "Approved-review routing: PASSED"
    )

    print(
        "Blocked-row exclusion: PASSED"
    )

    print(
        "Deterministic SQL typing: PASSED"
    )

    print(
        "Routed:",
        prepared[
            "routed_count"
        ],
    )

    print(
        "Blocked:",
        prepared[
            "blocked_count"
        ],
    )

    print(
        "Stage 22.6 smoke test passed."
    )


if __name__ == "__main__":
    main()

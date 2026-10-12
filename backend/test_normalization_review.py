from __future__ import annotations

from backend.normalization_review import (
    build_review_candidates,
)


def main() -> None:
    print(
        "Stage 22.5 smoke test"
    )

    print(
        "=" * 50
    )

    validation_result = {
        "filename": "demo.csv",
        "candidate_record_count": 3,
        "accepted_count": 1,
        "needs_review_count": 1,
        "rejected_count": 1,
        "records": [
            {
                "source_row_number": 1,
                "source_column": "data",
                "raw_text": "good",
                "validation_status": "accepted",
                "raw_fields": {
                    "date": "2026-10-01",
                    "sales": "250000",
                },
                "normalized_fields": {
                    "date": "2026-10-01",
                    "sales": 250000.0,
                },
                "warnings": [],
                "errors": [],
            },
            {
                "source_row_number": 2,
                "source_column": "data",
                "raw_text": "review",
                "validation_status": "needs_review",
                "raw_fields": {
                    "date": "2026-10-02",
                    "sales": "180000",
                    "unknown": "ABC",
                },
                "normalized_fields": {
                    "date": "2026-10-02",
                    "sales": 180000.0,
                    "unknown": "ABC",
                },
                "warnings": [
                    "Unknown field requires review."
                ],
                "errors": [],
            },
            {
                "source_row_number": 3,
                "source_column": "data",
                "raw_text": "bad",
                "validation_status": "rejected",
                "raw_fields": {
                    "date": "bad-date",
                },
                "normalized_fields": {},
                "warnings": [],
                "errors": [
                    "Invalid date."
                ],
            },
        ],
    }

    result = build_review_candidates(
        validation_result
    )

    rows = result[
        "records"
    ]

    assert (
        rows[0][
            "routing_status"
        ]
        == "eligible_for_routing"
    )

    assert (
        rows[1][
            "routing_status"
        ]
        == "needs_human_review"
    )

    assert (
        rows[2][
            "routing_status"
        ]
        == "blocked"
    )

    assert (
        result[
            "eligible_for_routing_count"
        ]
        == 1
    )

    assert (
        result[
            "human_review_count"
        ]
        == 1
    )

    assert (
        result[
            "blocked_count"
        ]
        == 1
    )

    print(
        "High-confidence accepted routing: PASSED"
    )

    print(
        "Ambiguous review routing: PASSED"
    )

    print(
        "Rejected record blocking: PASSED"
    )

    print(
        "Eligible:",
        result[
            "eligible_for_routing_count"
        ],
    )

    print(
        "Needs human review:",
        result[
            "human_review_count"
        ],
    )

    print(
        "Blocked:",
        result[
            "blocked_count"
        ],
    )

    print(
        "Next stage:",
        result[
            "next_stage"
        ],
    )

    print(
        "Stage 22.5 smoke test passed."
    )


if __name__ == "__main__":
    main()

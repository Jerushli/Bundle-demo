from __future__ import annotations

from backend.extraction_validator import (
    validate_extracted_candidates,
)


def main() -> None:
    print(
        "Stage 22.4 smoke test"
    )

    print(
        "=" * 50
    )

    extraction = {
        "filename": "demo.csv",
        "extractor_version": "22.3",
        "records": [
            {
                "source_row_number": 1,
                "source_column": "data",
                "raw_text": "good row",
                "extraction_status": "candidate_extracted",
                "fields": {
                    "date": "01-10-2026",
                    "region": "South India",
                    "product": "Laptop",
                    "sales": "250000",
                    "profit": "45000",
                },
            },
            {
                "source_row_number": 2,
                "source_column": "data",
                "raw_text": "bad row",
                "extraction_status": "candidate_extracted",
                "fields": {
                    "date": "not-a-date",
                    "region": "North India",
                    "sales": "not-money",
                },
            },
            {
                "source_row_number": 3,
                "source_column": "data",
                "raw_text": "unknown field row",
                "extraction_status": "candidate_extracted",
                "fields": {
                    "date": "2026-10-03",
                    "region": "West India",
                    "sales": "120000",
                    "unexpected_metric": "ABC",
                },
            },
        ],
    }

    result = validate_extracted_candidates(
        extraction
    )

    statuses = [
        item[
            "validation_status"
        ]
        for item in result[
            "records"
        ]
    ]

    assert statuses[
        0
    ] == "accepted"

    assert statuses[
        1
    ] == "rejected"

    assert statuses[
        2
    ] == "needs_review"

    first = result[
        "records"
    ][
        0
    ][
        "normalized_fields"
    ]

    assert (
        first[
            "date"
        ]
        == "2026-10-01"
    )

    assert (
        first[
            "sales"
        ]
        == 250000.0
    )

    print(
        "Accepted row validation: PASSED"
    )

    print(
        "Invalid date/numeric rejection: PASSED"
    )

    print(
        "Unknown field review routing: PASSED"
    )

    print(
        "Accepted:",
        result[
            "accepted_count"
        ],
    )

    print(
        "Needs review:",
        result[
            "needs_review_count"
        ],
    )

    print(
        "Rejected:",
        result[
            "rejected_count"
        ],
    )

    print(
        "Next stage:",
        result[
            "next_stage"
        ],
    )

    print(
        "Stage 22.4 smoke test passed."
    )


if __name__ == "__main__":
    main()

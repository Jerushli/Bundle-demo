from __future__ import annotations

import tempfile
from pathlib import Path

from backend.text_structure_extractor import (
    extract_key_value_pairs,
    extract_structured_candidates,
)


DEMO = """data
"Date: 01-10-2026, Region: South India, Product: Laptop, Sales: 250000, Profit: 45000, Note: strong demand but stock was unavailable for two days"
"Date: 02-10-2026, Region: North India, Product: Phone, Sales: 180000, Profit: 32000, Note: delayed distributor confirmation affected some orders"
"""


def main() -> None:
    print(
        "Stage 22.3 smoke test"
    )

    print(
        "=" * 50
    )

    pairs = extract_key_value_pairs(
        "Customer: ABC, Priority: High, Issue: Stock shortage, Owner: Ravi"
    )

    assert (
        pairs[
            "customer"
        ]
        == "ABC"
    )

    assert (
        pairs[
            "priority"
        ]
        == "High"
    )

    assert (
        pairs[
            "owner"
        ]
        == "Ravi"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        encoding="utf-8",
        newline="",
        delete=False,
    ) as temp:
        temp.write(
            DEMO
        )

        path = Path(
            temp.name
        )

    try:
        result = extract_structured_candidates(
            path
        )

    finally:
        path.unlink(
            missing_ok=True
        )

    assert (
        result[
            "status"
        ]
        == "candidates_ready_for_validation"
    )

    assert (
        result[
            "successful_extractions"
        ]
        == 2
    )

    first = result[
        "records"
    ][
        0
    ][
        "fields"
    ]

    assert (
        first[
            "region"
        ]
        == "South India"
    )

    assert (
        first[
            "sales"
        ]
        == "250000"
    )

    assert (
        first[
            "profit"
        ]
        == "45000"
    )

    print(
        "Key/value parser: PASSED"
    )

    print(
        "Successful extractions:",
        result[
            "successful_extractions"
        ],
    )

    print(
        "Discovered fields:",
        [
            item[
                "field_name"
            ]
            for item in result[
                "discovered_fields"
            ]
        ],
    )

    print(
        "Next stage:",
        result[
            "next_stage"
        ],
    )

    print(
        "Stage 22.3 smoke test passed."
    )


if __name__ == "__main__":
    main()

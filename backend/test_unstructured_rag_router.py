from __future__ import annotations

import tempfile
from pathlib import Path

from backend.unstructured_rag_router import (
    collect_rag_candidates,
)


CSV_TEXT = """date,region,sales,manager_notes,embedded_details
2026-10-01,South India,250000,"Strong distributor demand was reported during the week, but several outlets also mentioned temporary stock shortages.","Customer: ABC, Sales: 250000, Note: stock shortage"
2026-10-02,North India,180000,"Retail operations were normal overall, while several customers requested updated delivery estimates and additional support.","Customer: XYZ, Sales: 180000, Note: delivery delay"
"""


def main() -> None:
    print(
        "Stage 22.7 smoke test"
    )

    print(
        "=" * 50
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        encoding="utf-8",
        newline="",
        delete=False,
    ) as temp:
        temp.write(
            CSV_TEXT
        )

        path = Path(
            temp.name
        )

    try:
        result = collect_rag_candidates(
            path,
            dataset_name="demo_mixed_sales",
            access_level="internal",
        )

        embedded = collect_rag_candidates(
            path,
            dataset_name="demo_mixed_sales",
            access_level="restricted",
            include_embedded_structure=True,
        )

    finally:
        path.unlink(
            missing_ok=True
        )

    assert (
        "manager_notes"
        in result[
            "selected_columns"
        ]
    )

    assert (
        "embedded_details"
        not in result[
            "selected_columns"
        ]
    )

    assert (
        result[
            "candidate_count"
        ]
        == 2
    )

    assert all(
        item[
            "access_level"
        ]
        == "internal"
        for item in result[
            "candidates"
        ]
    )

    assert (
        "embedded_details"
        in embedded[
            "selected_columns"
        ]
    )

    print(
        "Narrative RAG selection: PASSED"
    )

    print(
        "Embedded structure excluded by default: PASSED"
    )

    print(
        "Explicit embedded inclusion: PASSED"
    )

    print(
        "Access metadata propagation: PASSED"
    )

    print(
        "Candidate count:",
        result[
            "candidate_count"
        ],
    )

    print(
        "Next stage:",
        result[
            "next_stage"
        ],
    )

    print(
        "Stage 22.7 smoke test passed."
    )


if __name__ == "__main__":
    main()

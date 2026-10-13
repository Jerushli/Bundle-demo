from __future__ import annotations

import tempfile
from pathlib import Path

from backend.input_file_classifier import classify_csv_file
from backend.mixed_content_detector import analyze_csv_columns
from backend.text_structure_extractor import extract_structured_candidates
from backend.extraction_validator import validate_extracted_candidates
from backend.normalization_review import build_review_candidates
from backend.unstructured_rag_router import collect_rag_candidates


DEMO = """record_id,date,region,segment,manager_notes,embedded_business_data
1,2026-10-01,South India,Enterprise,"Strong distributor demand was reported during the week, although two stores reported short stock availability.","Date: 01-10-2026, Region: South India, Product: Laptop, Sales: 250000, Profit: 45000, Note: strong demand"
2,2026-10-02,North India,SMB,"Several customers requested revised delivery estimates after a temporary logistics delay affected selected orders.","Date: 02-10-2026, Region: North India, Product: Phone, Sales: 180000, Profit: 32000, Note: delivery delay"
3,2026-10-03,West India,Enterprise,"Channel managers reported lower footfall while support teams handled multiple stock transfer requests.","Date: 03-10-2026, Region: West India, Product: Tablet, Sales: 120000, Profit: 22000, Note: lower footfall"
"""


def main() -> None:
    print(
        "Stage 22.9 smoke test"
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
            DEMO
        )

        path = Path(
            temp.name
        )

    try:
        classification = classify_csv_file(
            path
        )

        columns = analyze_csv_columns(
            path
        )

        extraction = extract_structured_candidates(
            path
        )

        validation = validate_extracted_candidates(
            extraction
        )

        review = build_review_candidates(
            validation
        )

        rag = collect_rag_candidates(
            path,
            dataset_name="stage22_e2e_test",
            access_level="internal",
        )

    finally:
        path.unlink(
            missing_ok=True
        )

    assert (
        classification[
            "classification"
        ]
        == "mixed"
    )

    assert (
        "manager_notes"
        in columns[
            "routing"
        ][
            "rag_columns"
        ]
    )

    assert (
        "embedded_business_data"
        in columns[
            "routing"
        ][
            "extraction_columns"
        ]
    )

    assert (
        extraction[
            "successful_extractions"
        ]
        == 3
    )

    assert (
        validation[
            "accepted_count"
        ]
        == 3
    )

    assert (
        review[
            "eligible_for_routing_count"
        ]
        == 3
    )

    assert (
        rag[
            "candidate_count"
        ]
        == 3
    )

    assert (
        "manager_notes"
        in rag[
            "selected_columns"
        ]
    )

    assert (
        "embedded_business_data"
        not in rag[
            "selected_columns"
        ]
    )

    print(
        "Input classification: PASSED"
    )

    print(
        "Mixed-content detection: PASSED"
    )

    print(
        "Structured extraction: PASSED"
    )

    print(
        "Deterministic validation: PASSED"
    )

    print(
        "Confidence routing: PASSED"
    )

    print(
        "Narrative RAG routing: PASSED"
    )

    print(
        "Numeric embedded text excluded from RAG: PASSED"
    )

    print(
        "Stage 22.9 smoke test passed."
    )


if __name__ == "__main__":
    main()

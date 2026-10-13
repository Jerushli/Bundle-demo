from __future__ import annotations
from backend.dynamic_schema_contract import propose_schema_contract, validate_with_contract

def main() -> None:
    extraction = {
        "records": [
            {
                "source_row_number": 1,
                "source_column": "embedded_business_data",
                "raw_text": "test",
                "extraction_status": "candidate_extracted",
                "fields": {
                    "date": "16-09-2025",
                    "region": "West",
                    "service": "Emergency Repair",
                    "revenue": "197798.05",
                    "profit": "68317.48",
                    "downtime": "10.87",
                    "sla": "No",
                    "note": "The SLA target was missed for this service event.",
                },
            },
            {
                "source_row_number": 2,
                "source_column": "embedded_business_data",
                "raw_text": "test",
                "extraction_status": "candidate_extracted",
                "fields": {
                    "date": "16-04-2024",
                    "region": "East",
                    "service": "Preventive Maintenance",
                    "revenue": "12176.46",
                    "profit": "5174.55",
                    "downtime": "0.93",
                    "sla": "Yes",
                    "note": "A supplier delivery delay affected selected repairs.",
                },
            },
        ]
    }

    proposal = propose_schema_contract(extraction, dataset_name="veyora_massive_test")
    types = {f["field_name"]: f["data_type"] for f in proposal["fields"]}

    assert types["date"] == "date"
    assert types["revenue"] == "decimal"
    assert types["downtime"] == "decimal"
    assert types["sla"] == "boolean"
    assert types["region"] == "categorical"

    contract = {
        "contract_id": 1,
        "dataset_name": "veyora_massive_test",
        "fields": proposal["fields"],
    }
    validated = validate_with_contract(extraction, contract)

    assert validated["accepted_count"] == 2
    assert validated["needs_review_count"] == 0
    assert validated["rejected_count"] == 0

    print("Stage 22.4.1 smoke test")
    print("=" * 50)
    print("Dynamic field inference: PASSED")
    print("Date inference: PASSED")
    print("Numeric inference: PASSED")
    print("Boolean inference: PASSED")
    print("Categorical inference: PASSED")
    print("Contract validation: PASSED")
    print("Accepted: 2")
    print("Needs review: 0")
    print("Rejected: 0")
    print("Stage 22.4.1 smoke test passed.")

if __name__ == "__main__":
    main()

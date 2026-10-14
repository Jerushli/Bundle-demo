from pathlib import Path
import csv
import tempfile

from backend.export_veyora_rag_evidence import (
    build_veyora_rag_candidates,
)

print(
    "Veyora source-CSV RAG exporter smoke test"
)
print("=" * 50)

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "sample.csv"

    rows = [
        {
            "region": "North",
            "manager_notes": "Workshop congestion increased waiting time.",
            "sla_met": "No",
            "downtime_hours": "8.5",
            "profit": "1000",
        },
        {
            "region": "North",
            "manager_notes": "Workshop congestion increased waiting time.",
            "sla_met": "Yes",
            "downtime_hours": "5.5",
            "profit": "1200",
        },
        {
            "region": "South",
            "manager_notes": "Supplier delay affected repairs.",
            "sla_met": "No",
            "downtime_hours": "7.0",
            "profit": "900",
        },
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "region",
                "manager_notes",
                "sla_met",
                "downtime_hours",
                "profit",
            ],
        )
        writer.writeheader()
        writer.writerows(
            rows
        )

    result = build_veyora_rag_candidates(
        path,
        dataset_name="veyora_massive",
        access_level="internal",
    )

    assert len(result) == 2

    north = [
        row
        for row in result
        if row["body"].startswith(
            "Region: North\n"
        )
    ]

    assert len(north) == 1
    assert "Observed in 2 service events" in north[0]["body"]
    assert "1 of those events missed SLA (50.00%)" in north[0]["body"]
    assert "Average downtime for these events is 7.00 hours" in north[0]["body"]

print("CSV aggregation: PASSED")
print("Region scoping: PASSED")
print("SLA aggregation: PASSED")
print("Downtime aggregation: PASSED")
print(
    "Veyora source-CSV RAG exporter smoke test passed."
)

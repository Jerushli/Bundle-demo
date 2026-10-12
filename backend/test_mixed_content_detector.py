import tempfile
from pathlib import Path
from backend.mixed_content_detector import analyze_csv_columns

DATA = """date,region,sales,manager_notes,embedded_details
2026-10-01,South India,250000,"Strong distributor demand was reported during the week, but several outlets also mentioned temporary stock shortages.","Customer: ABC, Priority: High, Issue: Stock shortage, Owner: Ravi"
2026-10-02,North India,180000,"Retail operations were normal overall, while several customers requested updated delivery estimates and support.","Customer: XYZ, Priority: Medium, Issue: Delivery delay, Owner: Priya"
2026-10-03,West India,120000,"Channel managers recorded lower footfall and multiple inventory transfer requests across several stores.","Customer: LMN, Priority: Low, Issue: Footfall, Owner: Arun"
"""

def main():
    print("Stage 22.2 smoke test")
    print("=" * 50)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", encoding="utf-8", newline="", delete=False) as temp:
        temp.write(DATA)
        path = Path(temp.name)
    try:
        result = analyze_csv_columns(path)
    finally:
        path.unlink(missing_ok=True)
    cols = {c["column_name"]: c for c in result["columns"]}
    assert cols["date"]["semantic_type"] == "date"
    assert cols["sales"]["semantic_type"] == "numeric"
    assert cols["manager_notes"]["semantic_type"] == "free_text"
    assert cols["manager_notes"]["rag_candidate"] is True
    assert cols["embedded_details"]["semantic_type"] == "embedded_structure"
    assert cols["embedded_details"]["extraction_required"] is True
    assert result["routing"]["file_route"] == "extract_embedded_structure_then_split"
    print("date ->", cols["date"]["semantic_type"])
    print("sales ->", cols["sales"]["semantic_type"])
    print("manager_notes ->", cols["manager_notes"]["semantic_type"])
    print("embedded_details ->", cols["embedded_details"]["semantic_type"])
    print("File route ->", result["routing"]["file_route"])
    print("Stage 22.2 smoke test passed.")

if __name__ == "__main__":
    main()


import tempfile
from pathlib import Path
from backend.input_file_classifier import classify_csv_file

STRUCTURED="""date,region,product,sales,profit,units
2026-10-01,South India,Laptop,250000,45000,12
2026-10-02,North India,Phone,180000,32000,20
2026-10-03,West India,Tablet,120000,22000,9
"""
MIXED="""date,region,sales,manager_notes
2026-10-01,South India,250000,"Strong demand reported by distributors and stock was unavailable for several outlets during part of the week, requiring follow-up."
2026-10-02,North India,180000,"Retail partners reported normal operations, though several customers requested updated delivery estimates and additional support."
"""
UNSTRUCTURED="""data
"Date: 01-10-2026, Region: South India, Product: Laptop, Sales: 250000, Profit: 45000, Note: strong demand but stock was unavailable for two days"
"Date: 02-10-2026, Region: North India, Product: Phone, Sales: 180000, Profit: 32000, Note: delayed distributor confirmation affected some orders"
"""

def run(content):
    with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",encoding="utf-8",newline="",delete=False) as f:
        f.write(content); path=Path(f.name)
    try: return classify_csv_file(path)
    finally: path.unlink(missing_ok=True)

def main():
    print("Stage 22.1 smoke test")
    print("="*50)
    s,m,u=run(STRUCTURED),run(MIXED),run(UNSTRUCTURED)
    print("Structured demo:",s["classification"])
    print("Mixed demo:",m["classification"])
    print("Unstructured demo:",u["classification"])
    assert s["classification"]=="structured"
    assert m["classification"]=="mixed"
    assert u["classification"]=="unstructured"
    print("Routing rules: PASSED")
    print("Stage 22.1 smoke test passed.")

if __name__=="__main__":
    main()

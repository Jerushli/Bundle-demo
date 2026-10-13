from __future__ import annotations
import argparse, json
from backend.dynamic_schema_contract import validate_csv_with_approved_contract

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("file_path")
    p.add_argument("--dataset-name", required=True)
    p.add_argument("--column", action="append", dest="columns")
    p.add_argument("--sample-rows", type=int, default=5000)
    a = p.parse_args()

    result = validate_csv_with_approved_contract(
        a.file_path,
        dataset_name=a.dataset_name,
        columns=a.columns,
        sample_rows=a.sample_rows,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()

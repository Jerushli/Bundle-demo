from __future__ import annotations
import argparse, json
from backend.dynamic_schema_contract import approve_schema_contract

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--contract-id", type=int, required=True)
    p.add_argument("--approved-by", default="cli-admin")
    a = p.parse_args()
    result = approve_schema_contract(a.contract_id, approved_by=a.approved_by)
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()

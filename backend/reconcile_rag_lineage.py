from __future__ import annotations
import argparse, json
from backend.normalization_lineage import reconcile_rag_mapping

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping_path")
    args = parser.parse_args()
    result = reconcile_rag_mapping(args.mapping_path, reconciled_by="cli")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()

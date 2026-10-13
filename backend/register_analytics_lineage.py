from __future__ import annotations
import argparse, json
from backend.normalization_lineage import register_analytics_lineage

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-id", type=int, required=True)
    args = parser.parse_args()
    result = register_analytics_lineage(route_id=args.route_id, created_by="cli")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()

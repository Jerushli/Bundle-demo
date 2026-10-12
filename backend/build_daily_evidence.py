from __future__ import annotations

import argparse
import json

from backend.daily_intelligence_evidence import build_daily_evidence_package


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Bundle Stage 21.3 daily intelligence evidence."
    )
    parser.add_argument(
        "--role",
        choices=["admin", "analyst", "viewer"],
        default="admin",
    )
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    result = build_daily_evidence_package(
        role=args.role,
        persist=not args.no_persist,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

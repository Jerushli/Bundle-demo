from __future__ import annotations

import argparse
import json

from backend.daily_intelligence_brief import (
    generate_daily_brief,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Bundle Stage 21.4 "
            "natural-language daily intelligence brief."
        )
    )

    parser.add_argument(
        "--role",
        choices=[
            "admin",
            "analyst",
            "viewer",
        ],
        default="admin",
    )

    parser.add_argument(
        "--no-persist",
        action="store_true",
    )

    args = parser.parse_args()

    result = generate_daily_brief(
        role=args.role,
        persist=not args.no_persist,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

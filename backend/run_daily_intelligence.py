from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.daily_intelligence_job import (
    run_daily_intelligence,
)


def _json_default(
    value: Any,
):
    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        Decimal,
    ):
        return float(
            value
        )

    raise TypeError(
        f"Object of type "
        f"{type(value).__name__} "
        f"is not JSON serializable"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete Bundle "
            "Stage 21 daily intelligence job."
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
        "--date",
        dest="run_date",
        help="Optional YYYY-MM-DD run date.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Run even when a successful "
            "job already exists for the date."
        ),
    )

    args = parser.parse_args()

    target_date = (
        date.fromisoformat(
            args.run_date
        )
        if args.run_date
        else None
    )

    result = run_daily_intelligence(
        role_name=args.role,
        run_date=target_date,
        force=args.force,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=_json_default,
        )
    )


if __name__ == "__main__":
    main()

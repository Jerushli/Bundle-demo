from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.daily_intelligence import generate_daily_snapshot


def _json_default(value: Any):
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic Bundle daily KPI snapshot."
    )

    parser.add_argument(
        "--date",
        dest="snapshot_date",
        help="Optional snapshot date in YYYY-MM-DD format.",
    )

    args = parser.parse_args()

    snapshot_date = (
        date.fromisoformat(args.snapshot_date)
        if args.snapshot_date
        else None
    )

    result = generate_daily_snapshot(
        snapshot_date=snapshot_date
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=_json_default,
        )
    )


if __name__ == "__main__":
    main()

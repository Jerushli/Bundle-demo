from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.intelligence_change_detection import detect_latest_changes


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
        description=(
            "Compare the latest two KPI snapshots and detect "
            "configured threshold breaches."
        )
    )

    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Calculate changes without storing change events.",
    )

    args = parser.parse_args()

    result = detect_latest_changes(
        persist=not args.no_persist
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

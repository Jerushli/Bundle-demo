from __future__ import annotations

import argparse
import json

from backend.structured_analytics_router import (
    route_structured_to_analytics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Route high-confidence normalized structured "
            "records into an isolated analytics staging table."
        )
    )

    parser.add_argument(
        "file_path"
    )

    parser.add_argument(
        "--dataset-name",
        required=True,
    )

    parser.add_argument(
        "--column",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--sample-rows",
        type=int,
        default=5000,
    )

    parser.add_argument(
        "--require-known-fields-only",
        action="store_true",
    )

    args = parser.parse_args()

    result = route_structured_to_analytics(
        args.file_path,
        dataset_name=args.dataset_name,
        columns=args.column,
        sample_rows=args.sample_rows,
        require_known_fields_only=args.require_known_fields_only,
        created_by="cli",
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

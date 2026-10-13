from __future__ import annotations

import argparse
import json

from backend.company_onboarding_test import (
    persist_onboarding_test,
    run_company_onboarding_test,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Bundle Stage 22.9 end-to-end company onboarding test."
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
        "--access-level",
        choices=[
            "public",
            "internal",
            "restricted",
        ],
        default="internal",
    )

    parser.add_argument(
        "--sample-rows",
        type=int,
        default=5000,
    )

    parser.add_argument(
        "--no-analytics-write",
        action="store_true",
    )

    parser.add_argument(
        "--no-rag-persist",
        action="store_true",
    )

    parser.add_argument(
        "--persist-run",
        action="store_true",
    )

    args = parser.parse_args()

    result = run_company_onboarding_test(
        args.file_path,
        dataset_name=args.dataset_name,
        access_level=args.access_level,
        sample_rows=args.sample_rows,
        persist_rag=not args.no_rag_persist,
        write_analytics=not args.no_analytics_write,
        created_by="cli",
    )

    if args.persist_run:
        result = persist_onboarding_test(
            result,
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

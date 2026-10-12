from __future__ import annotations

import argparse
import json

from backend.normalization_review import (
    persist_review_batch,
    run_confidence_review,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Score validated extraction candidates and "
            "prepare a deterministic human review batch."
        )
    )

    parser.add_argument(
        "file_path"
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
        "--dataset-name",
        default=None,
    )

    parser.add_argument(
        "--validation-run-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--require-known-fields-only",
        action="store_true",
    )

    parser.add_argument(
        "--persist",
        action="store_true",
    )

    args = parser.parse_args()

    result = run_confidence_review(
        args.file_path,
        columns=args.column,
        sample_rows=args.sample_rows,
        require_known_fields_only=args.require_known_fields_only,
    )

    if args.persist:
        result = persist_review_batch(
            result,
            dataset_name=args.dataset_name,
            validation_run_id=args.validation_run_id,
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

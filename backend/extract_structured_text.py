from __future__ import annotations

import argparse
import json

from backend.text_structure_extractor import (
    extract_structured_candidates,
    persist_extraction_run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract deterministic key:value structured "
            "candidates from embedded CSV text."
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
        "--analysis-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--persist",
        action="store_true",
    )

    args = parser.parse_args()

    result = extract_structured_candidates(
        args.file_path,
        columns=args.column,
        sample_rows=args.sample_rows,
    )

    if args.persist:
        result = persist_extraction_run(
            result,
            dataset_name=args.dataset_name,
            analysis_id=args.analysis_id,
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

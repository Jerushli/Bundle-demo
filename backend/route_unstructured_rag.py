from __future__ import annotations

import argparse
import json

from backend.unstructured_rag_router import (
    collect_rag_candidates,
    persist_rag_route,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare unstructured CSV text for secure RAG ingestion."
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
        "--include-embedded-structure",
        action="store_true",
    )

    parser.add_argument(
        "--persist",
        action="store_true",
    )

    args = parser.parse_args()

    result = collect_rag_candidates(
        args.file_path,
        dataset_name=args.dataset_name,
        access_level=args.access_level,
        sample_rows=args.sample_rows,
        include_embedded_structure=args.include_embedded_structure,
    )

    if args.persist:
        result = persist_rag_route(
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

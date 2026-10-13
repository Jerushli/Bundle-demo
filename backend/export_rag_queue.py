from __future__ import annotations

import argparse
import json

from backend.unstructured_rag_router import (
    export_pending_rag_queue,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export pending Bundle Stage 22.7 RAG queue items to JSONL."
        )
    )

    parser.add_argument(
        "--output",
        default=(
            "data/rag_stage22/"
            "pending_rag_documents.jsonl"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
    )

    args = parser.parse_args()

    result = export_pending_rag_queue(
        output_path=args.output,
        limit=args.limit,
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

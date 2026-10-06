"""Small JSON worker executed by Bundle's dedicated RAG Python environment."""

from __future__ import annotations

import argparse
import json
import sys

from backend.rag_retrieval import (
    rag_results_to_evidence,
    retrieve_allowed_chunks,
)


SENTINEL = "BUNDLE_RAG_JSON="


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--question",
        required=True,
    )

    parser.add_argument(
        "--role",
        required=True,
        choices=[
            "admin",
            "analyst",
            "viewer",
        ],
    )

    parser.add_argument(
        "--dataset",
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    try:
        results = retrieve_allowed_chunks(
            question=args.question,
            role=args.role,
            dataset_name=args.dataset,
            limit=args.limit,
        )

        payload = {
            "ok": True,
            "results": rag_results_to_evidence(
                results
            ),
        }

    except Exception as exc:
        payload = {
            "ok": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    print(
        SENTINEL
        + json.dumps(
            payload,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

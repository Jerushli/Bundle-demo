"""Permission-aware semantic-search test for Bundle RAG."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from backend.rag_retrieval import (
    retrieve_allowed_chunks,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument(
        "--role",
        choices=["admin", "analyst", "viewer"],
        default="analyst",
    )
    parser.add_argument(
        "--dataset",
        default="bundle_test_sales",
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    print(f"Query: {args.question}")
    print(f"Role: {args.role}")
    print(f"Dataset: {args.dataset}")

    results = retrieve_allowed_chunks(
        question=args.question,
        role=args.role,
        dataset_name=args.dataset,
        limit=args.limit,
    )

    if not results:
        print("No authorized semantic matches.")
        return

    print("\nAuthorized semantic matches:\n")

    for item in results:
        print(
            f"{item.document_id}"
            f" | {item.title}"
            f" | {item.document_type}"
            f" | dataset={item.dataset_name}"
            f" | access={item.access_level}"
            f" | similarity={item.similarity:.4f}"
        )


if __name__ == "__main__":
    main()

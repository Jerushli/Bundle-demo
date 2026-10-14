import argparse

from backend.dataset_transformer import (
    transform_dataset,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Transform a validated Bundle staging dataset "
            "into a typed analytics table."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset name used during Stage 1 ingestion.",
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Drop and rebuild an existing analytics table. "
            "Use intentionally."
        ),
    )

    args = parser.parse_args()

    result = transform_dataset(
        args.dataset,
        replace_existing=args.replace,
    )

    print()
    print("Bundle transformation completed")
    print("-------------------------------")
    print(f"Job ID:             {result.job_id}")
    print(f"Dataset:            {result.dataset_name}")
    print(f"Source:             {result.source_table}")
    print(f"Target:             {result.target_table}")
    print(f"Rows transformed:   {result.rows_transformed:,}")
    print(f"Rows quarantined:   {result.rows_quarantined:,}")
    print(f"Started:            {result.started_at.isoformat()}")
    print(f"Finished:           {result.finished_at.isoformat()}")


if __name__ == "__main__":
    main()

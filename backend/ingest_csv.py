import argparse
from pathlib import Path

from backend.ingestion import ingest_csv_dataset


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Stream one large CSV or multiple CSV parts "
            "into a Bundle staging table."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Logical dataset name, e.g. enterprise_sales",
    )

    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help=(
            "CSV file or directory. Repeat --input "
            "for multiple paths."
        ),
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=100_000,
        help="Update job progress every N rows.",
    )

    args = parser.parse_args()

    result = ingest_csv_dataset(
        dataset_name=args.dataset,
        input_paths=[Path(value) for value in args.input],
        progress_every=args.progress_every,
    )

    print()
    print("Bundle ingestion completed")
    print("--------------------------")
    print(f"Job ID:          {result.job_id}")
    print(f"Dataset:         {result.dataset_name}")
    print(f"Staging table:   {result.staging_table}")
    print(f"Files processed: {result.files_processed}")
    print(f"Rows loaded:     {result.rows_loaded:,}")
    print(f"Started:         {result.started_at.isoformat()}")
    print(f"Finished:        {result.finished_at.isoformat()}")


if __name__ == "__main__":
    main()

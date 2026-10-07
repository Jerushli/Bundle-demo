from __future__ import annotations

import argparse
from pathlib import Path

from backend.dataset_pipeline import (
    create_pipeline_job,
    update_pipeline_job,
)
from backend.dataset_refresh import (
    run_dataset_refresh,
    technical_refresh_name,
)
from backend.ingestion import (
    sanitize_identifier,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run a safe refresh of an existing Bundle dataset. "
            "Suitable for Windows Task Scheduler or another external scheduler."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Logical registered dataset name.",
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to the new CSV snapshot.",
    )

    args = parser.parse_args()

    dataset_name = sanitize_identifier(
        args.dataset
    )

    csv_path = Path(
        args.file
    ).expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(
            csv_path
        )

    if csv_path.suffix.lower() != ".csv":
        raise ValueError(
            "Refresh input must be a CSV file."
        )

    # First create the job to obtain a stable job/version number.
    job_id = create_pipeline_job(
        dataset_name=dataset_name,
        original_filename=(
            csv_path.name
        ),
        uploaded_path=str(
            csv_path
        ),
        job_type="refresh",
        technical_dataset_name=None,
    )

    technical_name = technical_refresh_name(
        dataset_name,
        job_id,
    )

    # Store the technical name after job ID allocation.
    from backend.ingestion import (
        get_ingest_connection,
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE bundle.pipeline_jobs
                SET
                    technical_dataset_name = %s,
                    status = 'queued',
                    current_stage = 'queued',
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    technical_name,
                    job_id,
                ),
            )

            connection.commit()

    print(
        f"Refresh job {job_id} created for {dataset_name}.",
        flush=True,
    )

    run_dataset_refresh(
        job_id=job_id,
        dataset_name=dataset_name,
        uploaded_path=str(
            csv_path
        ),
        original_filename=(
            csv_path.name
        ),
    )

    print(
        f"Refresh job {job_id} completed successfully.",
        flush=True,
    )


if __name__ == "__main__":
    main()

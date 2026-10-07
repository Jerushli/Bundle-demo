from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.business_profiler import (
    profile_business_dataset,
)
from backend.dataset_registry import (
    update_dataset_lifecycle,
)
from backend.dataset_transformer import (
    transform_dataset,
)
from backend.dataset_validator import (
    validate_dataset,
)
from backend.ingestion import (
    get_ingest_connection,
    ingest_csv_dataset,
    sanitize_identifier,
)
from backend.schema_profiler import (
    profile_dataset,
)


PIPELINE_STAGES = {
    "queued",
    "uploading",
    "ingesting",
    "profiling",
    "validating",
    "transforming",
    "business_profiling",
    "quality_check",
    "promoting",
    "ready",
    "failed",
}


def create_pipeline_job(
    *,
    dataset_name: str,
    original_filename: str,
    uploaded_path: str | None = None,
    job_type: str = "create",
    technical_dataset_name: str | None = None,
) -> int:
    clean_name = sanitize_identifier(
        dataset_name
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.pipeline_jobs
                (
                    dataset_name,
                    original_filename,
                    uploaded_path,
                    job_type,
                    technical_dataset_name,
                    status,
                    current_stage,
                    created_at,
                    updated_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'uploading',
                    'uploading',
                    now(),
                    now()
                )
                RETURNING id
                """,
                (
                    clean_name,
                    original_filename,
                    uploaded_path,
                    job_type,
                    technical_dataset_name,
                ),
            )

            job_id = int(
                cur.fetchone()[0]
            )

            connection.commit()

    return job_id


def update_pipeline_job(
    job_id: int,
    *,
    status: str | None = None,
    current_stage: str | None = None,
    uploaded_path: str | None = None,
    rows_loaded: int | None = None,
    rows_transformed: int | None = None,
    rows_quarantined: int | None = None,
    error_message: str | None = None,
    finished: bool = False,
):
    if status is not None and status not in PIPELINE_STAGES:
        raise ValueError(
            f"Unsupported pipeline status: {status}"
        )

    if current_stage is not None and current_stage not in PIPELINE_STAGES:
        raise ValueError(
            f"Unsupported pipeline stage: {current_stage}"
        )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE bundle.pipeline_jobs
                SET
                    status =
                        COALESCE(%s, status),
                    current_stage =
                        COALESCE(%s, current_stage),
                    uploaded_path =
                        COALESCE(%s, uploaded_path),
                    rows_loaded =
                        COALESCE(%s, rows_loaded),
                    rows_transformed =
                        COALESCE(%s, rows_transformed),
                    rows_quarantined =
                        COALESCE(%s, rows_quarantined),
                    error_message = %s,
                    started_at =
                        CASE
                            WHEN started_at IS NULL
                                 AND %s NOT IN (
                                     'uploading',
                                     'queued'
                                 )
                            THEN now()
                            ELSE started_at
                        END,
                    finished_at =
                        CASE
                            WHEN %s
                            THEN now()
                            ELSE finished_at
                        END,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    status,
                    current_stage,
                    uploaded_path,
                    rows_loaded,
                    rows_transformed,
                    rows_quarantined,
                    error_message,
                    current_stage,
                    finished,
                    job_id,
                ),
            )

            if cur.rowcount != 1:
                raise ValueError(
                    f"Pipeline job {job_id} does not exist."
                )

            connection.commit()


def get_pipeline_job(
    job_id: int,
) -> dict[str, Any] | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    dataset_name,
                    original_filename,
                    uploaded_path,
                    job_type,
                    technical_dataset_name,
                    status,
                    current_stage,
                    rows_loaded,
                    rows_transformed,
                    rows_quarantined,
                    error_message,
                    created_at,
                    started_at,
                    finished_at,
                    updated_at
                FROM bundle.pipeline_jobs
                WHERE id = %s
                LIMIT 1
                """,
                (job_id,),
            )

            row = cur.fetchone()

    if not row:
        return None

    return {
        "id": int(row[0]),
        "dataset_name": str(row[1]),
        "original_filename": str(row[2]),
        "uploaded_path": (
            str(row[3])
            if row[3] is not None
            else None
        ),
        "job_type": str(row[4]),
        "technical_dataset_name": (
            str(row[5])
            if row[5] is not None
            else None
        ),
        "status": str(row[6]),
        "current_stage": str(row[7]),
        "rows_loaded": (
            int(row[8])
            if row[8] is not None
            else None
        ),
        "rows_transformed": (
            int(row[9])
            if row[9] is not None
            else None
        ),
        "rows_quarantined": (
            int(row[10])
            if row[10] is not None
            else None
        ),
        "error_message": (
            str(row[11])
            if row[11] is not None
            else None
        ),
        "created_at": row[12],
        "started_at": row[13],
        "finished_at": row[14],
        "updated_at": row[15],
    }


def list_pipeline_jobs(
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(
            int(limit),
            200,
        ),
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id
                FROM bundle.pipeline_jobs
                ORDER BY id DESC
                LIMIT %s
                """,
                (safe_limit,),
            )

            ids = [
                int(row[0])
                for row in cur.fetchall()
            ]

    return [
        job
        for job_id in ids
        if (
            job := get_pipeline_job(
                job_id
            )
        ) is not None
    ]


def _install_default_permissions(
    *,
    dataset_name: str,
    validation_report,
):
    """
    Create safe default permissions for a newly prepared dataset.

    Admin:
        all validated structured columns

    Analyst:
        structured columns, excluding RAG/free-text candidates

    Viewer:
        same structured subset, but only aggregate/group operations.
        Viewer still cannot use /api/chat under the current application RBAC.
    """
    structured_columns = [
        column.column_name
        for column in validation_report.columns
        if (
            not column.rag_candidate
            and column.proposed_role
            not in {
                "free_text",
                "high_cardinality_text",
            }
        )
    ]

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO security.dataset_permissions
                (
                    dataset_name,
                    role,
                    can_read,
                    allowed_columns,
                    allowed_operations,
                    max_result_rows
                )
                VALUES
                (
                    %s,
                    'admin',
                    TRUE,
                    NULL,
                    ARRAY[
                        'aggregate',
                        'group',
                        'compare',
                        'trend'
                    ]::TEXT[],
                    100
                ),
                (
                    %s,
                    'analyst',
                    TRUE,
                    %s,
                    ARRAY[
                        'aggregate',
                        'group',
                        'compare',
                        'trend'
                    ]::TEXT[],
                    20
                ),
                (
                    %s,
                    'viewer',
                    TRUE,
                    %s,
                    ARRAY[
                        'aggregate',
                        'group'
                    ]::TEXT[],
                    10
                )
                ON CONFLICT (
                    dataset_name,
                    role
                )
                DO UPDATE SET
                    can_read =
                        EXCLUDED.can_read,
                    allowed_columns =
                        EXCLUDED.allowed_columns,
                    allowed_operations =
                        EXCLUDED.allowed_operations,
                    max_result_rows =
                        EXCLUDED.max_result_rows,
                    updated_at =
                        now()
                """,
                (
                    dataset_name,
                    dataset_name,
                    structured_columns,
                    dataset_name,
                    structured_columns,
                ),
            )

            connection.commit()


def run_dataset_pipeline(
    *,
    job_id: int,
    dataset_name: str,
    uploaded_path: str,
):
    clean_name = sanitize_identifier(
        dataset_name
    )

    source_path = Path(
        uploaded_path
    )

    try:
        # -------------------------------------------------
        # STAGE 1 — INGESTION
        # -------------------------------------------------
        update_pipeline_job(
            job_id,
            status="ingesting",
            current_stage="ingesting",
            error_message=None,
        )

        update_dataset_lifecycle(
            dataset_name=clean_name,
            status="ingesting",
            error_message=None,
        )

        ingestion = ingest_csv_dataset(
            dataset_name=clean_name,
            input_paths=[
                source_path
            ],
        )

        update_pipeline_job(
            job_id,
            rows_loaded=(
                ingestion.rows_loaded
            ),
        )

        # -------------------------------------------------
        # STAGE 2 — PROFILING
        # -------------------------------------------------
        update_pipeline_job(
            job_id,
            status="profiling",
            current_stage="profiling",
        )

        profile = profile_dataset(
            dataset_name=clean_name,
            sample_size=50000,
        )

        update_dataset_lifecycle(
            dataset_name=clean_name,
            status="profiled",
            row_count=(
                profile.total_rows
            ),
        )

        # -------------------------------------------------
        # STAGE 3 — FULL VALIDATION
        # -------------------------------------------------
        update_pipeline_job(
            job_id,
            status="validating",
            current_stage="validating",
        )

        validation = validate_dataset(
            dataset_name=clean_name,
            full_validation=True,
        )

        if not validation.ready_for_transform:
            warning_text = "; ".join(
                validation.warnings
            )

            raise ValueError(
                "Dataset validation did not approve transformation."
                + (
                    f" Warnings: {warning_text}"
                    if warning_text
                    else ""
                )
            )

        update_dataset_lifecycle(
            dataset_name=clean_name,
            status="validated",
        )

        # -------------------------------------------------
        # STAGE 4 — TRANSFORM
        # -------------------------------------------------
        update_pipeline_job(
            job_id,
            status="transforming",
            current_stage="transforming",
        )

        transformation = transform_dataset(
            dataset_name=clean_name,
            replace_existing=False,
        )

        update_pipeline_job(
            job_id,
            rows_transformed=(
                transformation.rows_transformed
            ),
            rows_quarantined=(
                transformation.rows_quarantined
            ),
        )

        update_dataset_lifecycle(
            dataset_name=clean_name,
            status="transforming",
            row_count=(
                transformation.rows_transformed
            ),
            analytics_table=(
                transformation.target_table
            ),
        )

        # Default access permissions are required before
        # the dataset can later be activated.
        _install_default_permissions(
            dataset_name=clean_name,
            validation_report=validation,
        )

        # -------------------------------------------------
        # STAGE 5 — BUSINESS PROFILE
        # -------------------------------------------------
        update_pipeline_job(
            job_id,
            status="business_profiling",
            current_stage="business_profiling",
        )

        business_profile = (
            profile_business_dataset(
                dataset_name=clean_name,
            )
        )

        update_dataset_lifecycle(
            dataset_name=clean_name,
            status="ready",
            row_count=(
                business_profile.total_rows
            ),
            analytics_table=(
                business_profile.analytics_table
            ),
            error_message=None,
            refreshed=True,
        )

        update_pipeline_job(
            job_id,
            status="ready",
            current_stage="ready",
            error_message=None,
            finished=True,
        )

    except Exception as exc:
        error_text = (
            f"{type(exc).__name__}: {exc}"
        )[:2000]

        try:
            update_dataset_lifecycle(
                dataset_name=clean_name,
                status="failed",
                error_message=(
                    error_text
                ),
            )
        except Exception:
            pass

        try:
            update_pipeline_job(
                job_id,
                status="failed",
                current_stage="failed",
                error_message=(
                    error_text
                ),
                finished=True,
            )
        except Exception:
            pass

        # BackgroundTasks exceptions should still be visible
        # in the backend logs for development troubleshooting.
        raise

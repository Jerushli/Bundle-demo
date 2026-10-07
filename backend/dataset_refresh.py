from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg import sql

from backend.business_profiler import (
    profile_business_dataset,
)
from backend.dataset_pipeline import (
    update_pipeline_job,
)
from backend.dataset_registry import (
    get_dataset,
)
from backend.dataset_transformer import (
    target_table_name,
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


def technical_refresh_name(
    logical_dataset_name: str,
    job_id: int,
) -> str:
    """
    Keep enough of the logical name for debugging while leaving room
    for the refresh suffix inside PostgreSQL identifier limits.
    """
    logical = sanitize_identifier(
        logical_dataset_name
    )

    suffix = f"_r{job_id}"

    return (
        logical[
            : max(
                1,
                50 - len(
                    suffix
                ),
            )
        ]
        + suffix
    )


def archive_table_name(
    logical_dataset_name: str,
    job_id: int,
) -> str:
    logical = sanitize_identifier(
        logical_dataset_name
    )

    suffix = (
        f"_before_r{job_id}"
    )

    return (
        f"{logical}_clean"[
            : max(
                1,
                60 - len(
                    suffix
                ),
            )
        ]
        + suffix
    )


def _latest_validation_report(
    *,
    dataset_name: str,
) -> dict[str, Any] | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT report_json
                FROM staging.validation_reports
                WHERE dataset_name = %s
                ORDER BY
                    CASE
                        WHEN validation_mode = 'full'
                        THEN 0
                        ELSE 1
                    END,
                    created_at DESC
                LIMIT 1
                """,
                (
                    sanitize_identifier(
                        dataset_name
                    ),
                ),
            )

            row = cur.fetchone()

    if not row:
        return None

    payload = row[0]

    if isinstance(
        payload,
        str,
    ):
        payload = json.loads(
            payload
        )

    return dict(
        payload
    )


def _schema_signature(
    report: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    signature: dict[
        str,
        tuple[str, str],
    ] = {}

    for column in report.get(
        "columns",
        [],
    ):
        name = str(
            column.get(
                "column_name",
                "",
            )
        )

        if not name:
            continue

        signature[name] = (
            str(
                column.get(
                    "proposed_type",
                    "",
                )
            ),
            str(
                column.get(
                    "proposed_role",
                    "",
                )
            ),
        )

    return signature


def _assert_refresh_schema_compatible(
    *,
    logical_dataset_name: str,
    new_validation_report,
):
    current = _latest_validation_report(
        dataset_name=logical_dataset_name
    )

    if not current:
        raise ValueError(
            "Current dataset has no Stage 3 validation report. "
            "A safe refresh cannot compare schemas."
        )

    old_signature = _schema_signature(
        current
    )

    new_signature = {
        column.column_name: (
            column.proposed_type,
            column.proposed_role,
        )
        for column
        in new_validation_report.columns
    }

    old_columns = set(
        old_signature
    )

    new_columns = set(
        new_signature
    )

    missing = sorted(
        old_columns
        - new_columns
    )

    added = sorted(
        new_columns
        - old_columns
    )

    changed = sorted(
        column
        for column
        in (
            old_columns
            & new_columns
        )
        if (
            old_signature[
                column
            ]
            != new_signature[
                column
            ]
        )
    )

    if (
        missing
        or added
        or changed
    ):
        parts = []

        if missing:
            parts.append(
                "missing columns: "
                + ", ".join(
                    missing[:20]
                )
            )

        if added:
            parts.append(
                "new columns: "
                + ", ".join(
                    added[:20]
                )
            )

        if changed:
            parts.append(
                "changed type/role: "
                + ", ".join(
                    changed[:20]
                )
            )

        raise ValueError(
            "Refresh schema differs from the current live dataset; "
            + "; ".join(
                parts
            )
            + ". Upload this as a new dataset or explicitly migrate "
              "the schema instead of silently replacing the live version."
        )


def _table_exists(
    connection,
    *,
    schema_name: str,
    table_name: str,
) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE
                    table_schema = %s
                    AND table_name = %s
            )
            """,
            (
                schema_name,
                table_name,
            ),
        )

        return bool(
            cur.fetchone()[0]
        )


def _copy_latest_profile_metadata(
    connection,
    *,
    technical_dataset_name: str,
    logical_dataset_name: str,
    logical_analytics_table: str,
):
    """
    Promote the latest technical Stage 2/3/5 metadata to the logical
    dataset identity. This is executed in the same transaction as
    the table rename.
    """
    with connection.cursor() as cur:
        # Stage 2 profile
        cur.execute(
            """
            SELECT
                staging_table,
                total_rows,
                sample_rows,
                column_count,
                profile_json
            FROM staging.dataset_profiles
            WHERE dataset_name = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                technical_dataset_name,
            ),
        )

        profile_row = cur.fetchone()

        if not profile_row:
            raise ValueError(
                "Technical refresh has no Stage 2 profile."
            )

        profile_json = profile_row[4]

        if isinstance(
            profile_json,
            str,
        ):
            profile_json = json.loads(
                profile_json
            )

        profile_json = dict(
            profile_json
        )

        profile_json[
            "dataset_name"
        ] = logical_dataset_name

        cur.execute(
            """
            INSERT INTO staging.dataset_profiles
            (
                dataset_name,
                staging_table,
                total_rows,
                sample_rows,
                column_count,
                profile_json,
                created_at
            )
            VALUES
            (
                %s, %s, %s, %s, %s, %s, now()
            )
            """,
            (
                logical_dataset_name,
                profile_row[0],
                profile_row[1],
                profile_row[2],
                profile_row[3],
                json.dumps(
                    profile_json
                ),
            ),
        )

        # Stage 3 validation
        cur.execute(
            """
            SELECT
                staging_table,
                validation_mode,
                ready_for_transform,
                report_json
            FROM staging.validation_reports
            WHERE dataset_name = %s
            ORDER BY
                CASE
                    WHEN validation_mode = 'full'
                    THEN 0
                    ELSE 1
                END,
                created_at DESC
            LIMIT 1
            """,
            (
                technical_dataset_name,
            ),
        )

        validation_row = cur.fetchone()

        if not validation_row:
            raise ValueError(
                "Technical refresh has no Stage 3 validation report."
            )

        validation_json = validation_row[3]

        if isinstance(
            validation_json,
            str,
        ):
            validation_json = json.loads(
                validation_json
            )

        validation_json = dict(
            validation_json
        )

        validation_json[
            "dataset_name"
        ] = logical_dataset_name

        cur.execute(
            """
            INSERT INTO staging.validation_reports
            (
                dataset_name,
                staging_table,
                validation_mode,
                ready_for_transform,
                report_json,
                created_at
            )
            VALUES
            (
                %s, %s, %s, %s, %s, now()
            )
            """,
            (
                logical_dataset_name,
                validation_row[0],
                validation_row[1],
                validation_row[2],
                json.dumps(
                    validation_json
                ),
            ),
        )

        # Stage 5 business profile
        cur.execute(
            """
            SELECT
                total_rows,
                primary_measure,
                quick_summary,
                profile_json
            FROM analytics.dataset_business_profiles
            WHERE dataset_name = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                technical_dataset_name,
            ),
        )

        business_row = cur.fetchone()

        if not business_row:
            raise ValueError(
                "Technical refresh has no Stage 5 business profile."
            )

        business_json = business_row[3]

        if isinstance(
            business_json,
            str,
        ):
            business_json = json.loads(
                business_json
            )

        business_json = dict(
            business_json
        )

        business_json[
            "dataset_name"
        ] = logical_dataset_name

        business_json[
            "analytics_table"
        ] = logical_analytics_table

        cur.execute(
            """
            INSERT INTO analytics.dataset_business_profiles
            (
                dataset_name,
                analytics_table,
                total_rows,
                primary_measure,
                quick_summary,
                profile_json,
                created_at
            )
            VALUES
            (
                %s, %s, %s, %s, %s, %s, now()
            )
            """,
            (
                logical_dataset_name,
                logical_analytics_table,
                business_row[0],
                business_row[1],
                business_row[2],
                json.dumps(
                    business_json
                ),
            ),
        )


def _promote_refresh(
    *,
    job_id: int,
    logical_dataset_name: str,
    technical_dataset_name: str,
    original_filename: str,
    row_count: int,
) -> str:
    logical_table = target_table_name(
        logical_dataset_name
    )

    technical_table = target_table_name(
        technical_dataset_name
    )

    archive_table = archive_table_name(
        logical_dataset_name,
        job_id,
    )

    logical_qualified = (
        f"analytics.{logical_table}"
    )

    with get_ingest_connection() as connection:
        # All following operations are one transaction.
        with connection.cursor() as cur:
            # Prevent two refresh promotions for the same logical dataset
            # from racing each other.
            cur.execute(
                """
                SELECT id
                FROM bundle.dataset_registry
                WHERE dataset_name = %s
                FOR UPDATE
                """,
                (
                    logical_dataset_name,
                ),
            )

            if not cur.fetchone():
                raise ValueError(
                    f"Dataset {logical_dataset_name!r} is not registered."
                )

            if not _table_exists(
                connection,
                schema_name="analytics",
                table_name=logical_table,
            ):
                raise ValueError(
                    f"Current live table analytics.{logical_table} does not exist."
                )

            if not _table_exists(
                connection,
                schema_name="analytics",
                table_name=technical_table,
            ):
                raise ValueError(
                    f"Prepared refresh table analytics.{technical_table} does not exist."
                )

            if _table_exists(
                connection,
                schema_name="analytics",
                table_name=archive_table,
            ):
                raise ValueError(
                    f"Archive table analytics.{archive_table} already exists."
                )

            cur.execute(
                sql.SQL(
                    "ALTER TABLE analytics.{} RENAME TO {}"
                ).format(
                    sql.Identifier(
                        logical_table
                    ),
                    sql.Identifier(
                        archive_table
                    ),
                )
            )

            cur.execute(
                sql.SQL(
                    "ALTER TABLE analytics.{} RENAME TO {}"
                ).format(
                    sql.Identifier(
                        technical_table
                    ),
                    sql.Identifier(
                        logical_table
                    ),
                )
            )

            _copy_latest_profile_metadata(
                connection,
                technical_dataset_name=(
                    technical_dataset_name
                ),
                logical_dataset_name=(
                    logical_dataset_name
                ),
                logical_analytics_table=(
                    logical_qualified
                ),
            )

            cur.execute(
                """
                UPDATE bundle.dataset_registry
                SET
                    analytics_table = %s,
                    status = 'ready',
                    row_count = %s,
                    source_name = %s,
                    last_refreshed_at = now(),
                    error_message = NULL,
                    updated_at = now()
                WHERE dataset_name = %s
                """,
                (
                    logical_qualified,
                    row_count,
                    original_filename,
                    logical_dataset_name,
                ),
            )

            cur.execute(
                """
                INSERT INTO bundle.dataset_versions
                (
                    dataset_name,
                    refresh_job_id,
                    source_name,
                    live_table,
                    archived_table,
                    row_count,
                    promoted_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, now()
                )
                """,
                (
                    logical_dataset_name,
                    job_id,
                    original_filename,
                    logical_qualified,
                    (
                        "analytics."
                        + archive_table
                    ),
                    row_count,
                ),
            )

        connection.commit()

    return (
        "analytics."
        + archive_table
    )


def run_dataset_refresh(
    *,
    job_id: int,
    dataset_name: str,
    uploaded_path: str,
    original_filename: str,
):
    logical_name = sanitize_identifier(
        dataset_name
    )

    record = get_dataset(
        logical_name
    )

    if not record:
        raise ValueError(
            f"Dataset {logical_name!r} is not registered."
        )

    if record.status != "ready":
        raise ValueError(
            f"Dataset {logical_name!r} must be READY before refresh."
        )

    technical_name = technical_refresh_name(
        logical_name,
        job_id,
    )

    source_path = Path(
        uploaded_path
    )

    try:
        # -------------------------------
        # Stage 1 — isolated ingestion
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="ingesting",
            current_stage="ingesting",
            error_message=None,
        )

        ingestion = ingest_csv_dataset(
            dataset_name=technical_name,
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

        # -------------------------------
        # Stage 2 — isolated profile
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="profiling",
            current_stage="profiling",
        )

        profile = profile_dataset(
            dataset_name=technical_name,
            sample_size=50000,
        )

        if profile.total_rows <= 0:
            raise ValueError(
                "Refresh contains zero data rows."
            )

        # -------------------------------
        # Stage 3 — isolated validation
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="validating",
            current_stage="validating",
        )

        validation = validate_dataset(
            dataset_name=technical_name,
            full_validation=True,
        )

        if not validation.ready_for_transform:
            warning_text = "; ".join(
                validation.warnings
            )

            raise ValueError(
                "Refresh validation did not approve transformation."
                + (
                    f" Warnings: {warning_text}"
                    if warning_text
                    else ""
                )
            )

        # -------------------------------
        # Quality gate
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="quality_check",
            current_stage="quality_check",
        )

        _assert_refresh_schema_compatible(
            logical_dataset_name=(
                logical_name
            ),
            new_validation_report=(
                validation
            ),
        )

        # -------------------------------
        # Stage 4 — isolated transform
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="transforming",
            current_stage="transforming",
        )

        transformation = transform_dataset(
            dataset_name=technical_name,
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

        if transformation.rows_transformed <= 0:
            raise ValueError(
                "Refresh produced zero transformed rows."
            )

        # -------------------------------
        # Stage 5 — isolated business profile
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="business_profiling",
            current_stage="business_profiling",
        )

        business_profile = (
            profile_business_dataset(
                dataset_name=technical_name,
            )
        )

        if business_profile.total_rows <= 0:
            raise ValueError(
                "Refresh business profile contains zero rows."
            )

        # -------------------------------
        # Atomic promotion
        # -------------------------------
        update_pipeline_job(
            job_id,
            status="promoting",
            current_stage="promoting",
        )

        archived_table = _promote_refresh(
            job_id=job_id,
            logical_dataset_name=(
                logical_name
            ),
            technical_dataset_name=(
                technical_name
            ),
            original_filename=(
                original_filename
            ),
            row_count=(
                business_profile.total_rows
            ),
        )

        update_pipeline_job(
            job_id,
            status="ready",
            current_stage="ready",
            error_message=None,
            finished=True,
        )

        print(
            "[dataset-refresh] "
            f"{logical_name} promoted successfully; "
            f"previous version retained at {archived_table}",
            flush=True,
        )

    except Exception as exc:
        error_text = (
            f"{type(exc).__name__}: {exc}"
        )[:2000]

        # CRITICAL:
        # Do not mark the logical dataset as failed.
        # Its previous validated version remains live.
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

        print(
            "[dataset-refresh] FAILED: "
            + error_text,
            flush=True,
        )

        raise

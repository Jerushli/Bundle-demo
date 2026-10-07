from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


DatasetStatus = Literal[
    "registered",
    "ingesting",
    "profiled",
    "validated",
    "transforming",
    "ready",
    "failed",
]


@dataclass(frozen=True)
class DatasetRecord:
    dataset_name: str
    display_name: str
    source_type: str
    source_name: str | None
    analytics_table: str | None
    status: str
    row_count: int | None
    is_active: bool
    last_refreshed_at: datetime | None
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    error_message: str | None


def _record_from_row(
    row: tuple[Any, ...],
) -> DatasetRecord:
    return DatasetRecord(
        dataset_name=str(row[0]),
        display_name=str(row[1]),
        source_type=str(row[2]),
        source_name=(
            str(row[3])
            if row[3] is not None
            else None
        ),
        analytics_table=(
            str(row[4])
            if row[4] is not None
            else None
        ),
        status=str(row[5]),
        row_count=(
            int(row[6])
            if row[6] is not None
            else None
        ),
        is_active=bool(row[7]),
        last_refreshed_at=row[8],
        activated_at=row[9],
        created_at=row[10],
        updated_at=row[11],
        error_message=(
            str(row[12])
            if row[12] is not None
            else None
        ),
    )


_SELECT_COLUMNS = """
    dataset_name,
    display_name,
    source_type,
    source_name,
    analytics_table,
    status,
    row_count,
    is_active,
    last_refreshed_at,
    activated_at,
    created_at,
    updated_at,
    error_message
"""


def dataset_to_dict(
    record: DatasetRecord,
) -> dict[str, Any]:
    return asdict(record)


def list_datasets() -> list[DatasetRecord]:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    {_SELECT_COLUMNS}
                FROM bundle.dataset_registry
                ORDER BY
                    is_active DESC,
                    display_name ASC,
                    dataset_name ASC
                """
            )

            return [
                _record_from_row(row)
                for row in cur.fetchall()
            ]


def get_dataset(
    dataset_name: str,
) -> DatasetRecord | None:
    clean_name = sanitize_identifier(
        dataset_name
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    {_SELECT_COLUMNS}
                FROM bundle.dataset_registry
                WHERE dataset_name = %s
                LIMIT 1
                """,
                (clean_name,),
            )

            row = cur.fetchone()

    return (
        _record_from_row(row)
        if row
        else None
    )


def get_active_dataset() -> DatasetRecord:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    {_SELECT_COLUMNS}
                FROM bundle.dataset_registry
                WHERE is_active = TRUE
                LIMIT 1
                """
            )

            row = cur.fetchone()

    if not row:
        raise ValueError(
            "No active Bundle dataset is configured. "
            "An administrator must activate a READY dataset."
        )

    record = _record_from_row(
        row
    )

    if record.status != "ready":
        raise ValueError(
            f"Active dataset {record.dataset_name!r} "
            f"is not READY (status={record.status!r})."
        )

    return record


def get_active_dataset_name() -> str:
    return get_active_dataset().dataset_name


def _analytics_table_exists(
    connection,
    analytics_table: str,
) -> bool:
    if "." in analytics_table:
        schema_name, table_name = (
            analytics_table.split(
                ".",
                1,
            )
        )
    else:
        schema_name = "analytics"
        table_name = analytics_table

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


def _business_profile_exists(
    connection,
    dataset_name: str,
) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM analytics.dataset_business_profiles
                WHERE dataset_name = %s
            )
            """,
            (dataset_name,),
        )

        return bool(
            cur.fetchone()[0]
        )


def _security_permissions_exist(
    connection,
    dataset_name: str,
) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT role)
            FROM security.dataset_permissions
            WHERE
                dataset_name = %s
                AND can_read = TRUE
                AND role IN (
                    'admin',
                    'analyst'
                )
            """,
            (dataset_name,),
        )

        count = int(
            cur.fetchone()[0]
            or 0
        )

    return count >= 2


def activate_dataset(
    dataset_name: str,
) -> DatasetRecord:
    clean_name = sanitize_identifier(
        dataset_name
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            # Serialize dataset activation so two admins cannot
            # race to activate different datasets.
            cur.execute(
                """
                LOCK TABLE
                    bundle.dataset_registry
                IN EXCLUSIVE MODE
                """
            )

            cur.execute(
                f"""
                SELECT
                    {_SELECT_COLUMNS}
                FROM bundle.dataset_registry
                WHERE dataset_name = %s
                FOR UPDATE
                """,
                (clean_name,),
            )

            row = cur.fetchone()

            if not row:
                raise ValueError(
                    f"Dataset {clean_name!r} is not registered."
                )

            target = _record_from_row(
                row
            )

            if target.status != "ready":
                raise ValueError(
                    f"Dataset {clean_name!r} cannot be activated "
                    f"because its status is {target.status!r}, not 'ready'."
                )

            if not target.analytics_table:
                raise ValueError(
                    "Dataset has no analytics table configured."
                )

            if not _analytics_table_exists(
                connection,
                target.analytics_table,
            ):
                raise ValueError(
                    f"Analytics table {target.analytics_table!r} "
                    "does not exist."
                )

            if not _business_profile_exists(
                connection,
                clean_name,
            ):
                raise ValueError(
                    "Dataset has no Stage 5 business profile."
                )

            if not _security_permissions_exist(
                connection,
                clean_name,
            ):
                raise ValueError(
                    "Dataset must have readable admin and analyst "
                    "security permissions before activation."
                )

            cur.execute(
                """
                UPDATE bundle.dataset_registry
                SET
                    is_active = FALSE,
                    updated_at = now()
                WHERE is_active = TRUE
                """
            )

            cur.execute(
                """
                UPDATE bundle.dataset_registry
                SET
                    is_active = TRUE,
                    activated_at = now(),
                    updated_at = now(),
                    error_message = NULL
                WHERE dataset_name = %s
                """,
                (clean_name,),
            )

            connection.commit()

    activated = get_dataset(
        clean_name
    )

    if not activated:
        raise RuntimeError(
            "Dataset activation completed but registry row "
            "could not be reloaded."
        )

    return activated


def register_existing_dataset(
    *,
    dataset_name: str,
    display_name: str,
    source_type: str = "existing_postgresql",
    source_name: str | None = None,
    analytics_table: str | None = None,
    status: DatasetStatus = "ready",
    row_count: int | None = None,
) -> DatasetRecord:
    clean_name = sanitize_identifier(
        dataset_name
    )

    clean_display = display_name.strip()

    if not clean_display:
        raise ValueError(
            "display_name cannot be empty."
        )

    if status not in {
        "registered",
        "ingesting",
        "profiled",
        "validated",
        "transforming",
        "ready",
        "failed",
    }:
        raise ValueError(
            f"Unsupported dataset status: {status}"
        )

    if analytics_table is None and status == "ready":
        analytics_table = (
            f"analytics.{clean_name}_clean"
        )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.dataset_registry
                (
                    dataset_name,
                    display_name,
                    source_type,
                    source_name,
                    analytics_table,
                    status,
                    row_count,
                    last_refreshed_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s,
                    CASE
                        WHEN %s = 'ready'
                        THEN now()
                        ELSE NULL
                    END
                )
                ON CONFLICT (dataset_name)
                DO UPDATE SET
                    display_name =
                        EXCLUDED.display_name,
                    source_type =
                        EXCLUDED.source_type,
                    source_name =
                        EXCLUDED.source_name,
                    analytics_table =
                        EXCLUDED.analytics_table,
                    status =
                        EXCLUDED.status,
                    row_count =
                        COALESCE(
                            EXCLUDED.row_count,
                            bundle.dataset_registry.row_count
                        ),
                    last_refreshed_at =
                        CASE
                            WHEN EXCLUDED.status = 'ready'
                            THEN COALESCE(
                                bundle.dataset_registry.last_refreshed_at,
                                now()
                            )
                            ELSE
                                bundle.dataset_registry.last_refreshed_at
                        END,
                    updated_at = now()
                """,
                (
                    clean_name,
                    clean_display,
                    source_type.strip(),
                    (
                        source_name.strip()
                        if source_name
                        else None
                    ),
                    analytics_table,
                    status,
                    row_count,
                    status,
                ),
            )

            connection.commit()

    record = get_dataset(
        clean_name
    )

    if not record:
        raise RuntimeError(
            "Dataset registration failed."
        )

    return record


def update_dataset_lifecycle(
    *,
    dataset_name: str,
    status: DatasetStatus,
    row_count: int | None = None,
    analytics_table: str | None = None,
    error_message: str | None = None,
    refreshed: bool = False,
) -> DatasetRecord:
    clean_name = sanitize_identifier(
        dataset_name
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE bundle.dataset_registry
                SET
                    status = %s,
                    row_count = COALESCE(
                        %s,
                        row_count
                    ),
                    analytics_table = COALESCE(
                        %s,
                        analytics_table
                    ),
                    error_message = %s,
                    last_refreshed_at =
                        CASE
                            WHEN %s
                            THEN now()
                            ELSE last_refreshed_at
                        END,
                    updated_at = now()
                WHERE dataset_name = %s
                """,
                (
                    status,
                    row_count,
                    analytics_table,
                    error_message,
                    refreshed,
                    clean_name,
                ),
            )

            if cur.rowcount != 1:
                raise ValueError(
                    f"Dataset {clean_name!r} is not registered."
                )

            connection.commit()

    record = get_dataset(
        clean_name
    )

    if not record:
        raise RuntimeError(
            "Dataset lifecycle update failed."
        )

    return record

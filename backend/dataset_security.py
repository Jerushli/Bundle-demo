from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


Role = Literal[
    "admin",
    "analyst",
    "viewer",
]


DEFAULT_MAX_RESULT_ROWS = 20
ABSOLUTE_MAX_RESULT_ROWS = 100


@dataclass(frozen=True)
class DatasetPermission:
    dataset_name: str
    role: Role
    can_read: bool
    allowed_columns: list[str] | None
    allowed_operations: list[str]
    max_result_rows: int


def _normalize_text_array(
    value: Any,
) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, list):
        return [
            str(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            str(item)
            for item in value
        ]

    return None


def get_dataset_permission(
    *,
    dataset_name: str,
    role: Role,
) -> DatasetPermission:
    clean_dataset = sanitize_identifier(
        dataset_name
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    can_read,
                    allowed_columns,
                    allowed_operations,
                    max_result_rows
                FROM security.dataset_permissions
                WHERE
                    dataset_name = %s
                    AND role = %s
                LIMIT 1
                """,
                (
                    clean_dataset,
                    role,
                ),
            )

            row = cur.fetchone()

    if not row:
        raise PermissionError(
            f"No dataset permission exists for role {role!r} "
            f"on dataset {clean_dataset!r}."
        )

    max_rows = int(
        row[3]
        or DEFAULT_MAX_RESULT_ROWS
    )

    max_rows = max(
        1,
        min(
            max_rows,
            ABSOLUTE_MAX_RESULT_ROWS,
        ),
    )

    return DatasetPermission(
        dataset_name=clean_dataset,
        role=role,
        can_read=bool(
            row[0]
        ),
        allowed_columns=(
            _normalize_text_array(
                row[1]
            )
        ),
        allowed_operations=(
            _normalize_text_array(
                row[2]
            )
            or []
        ),
        max_result_rows=max_rows,
    )


def enforce_dataset_access(
    *,
    permission: DatasetPermission,
):
    if not permission.can_read:
        raise PermissionError(
            f"Role {permission.role!r} does not have read access "
            f"to dataset {permission.dataset_name!r}."
        )


def filter_allowed_columns(
    *,
    permission: DatasetPermission,
    columns: list[str],
) -> list[str]:
    enforce_dataset_access(
        permission=permission
    )

    if (
        permission.allowed_columns
        is None
    ):
        return list(
            columns
        )

    allowed = set(
        permission.allowed_columns
    )

    return [
        column
        for column in columns
        if column in allowed
    ]


def enforce_column_access(
    *,
    permission: DatasetPermission,
    column: str | None,
):
    if column is None:
        return

    if (
        permission.allowed_columns
        is None
    ):
        return

    if (
        column
        not in permission.allowed_columns
    ):
        raise PermissionError(
            f"Role {permission.role!r} is not allowed to access "
            f"column {column!r} in dataset "
            f"{permission.dataset_name!r}."
        )


def enforce_operation_access(
    *,
    permission: DatasetPermission,
    operation: str,
):
    if (
        operation
        not in permission.allowed_operations
    ):
        raise PermissionError(
            f"Role {permission.role!r} is not allowed to run "
            f"operation {operation!r} on dataset "
            f"{permission.dataset_name!r}."
        )


def clamp_result_limit(
    *,
    permission: DatasetPermission,
    requested_limit: int,
) -> int:
    requested = max(
        1,
        int(
            requested_limit
            or 1
        ),
    )

    return min(
        requested,
        permission.max_result_rows,
        ABSOLUTE_MAX_RESULT_ROWS,
    )

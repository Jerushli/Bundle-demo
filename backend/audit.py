import os

from pathlib import Path

import psycopg

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)


AUDIT_DATABASE_URL = os.getenv(
    "AUDIT_DATABASE_URL"
)

# For local development this may point to the same database role.
# In production, prefer a separate read-only audit role.
AUDIT_READ_DATABASE_URL = os.getenv(
    "AUDIT_READ_DATABASE_URL",
    AUDIT_DATABASE_URL,
)


if not AUDIT_DATABASE_URL:
    raise RuntimeError(
        "AUDIT_DATABASE_URL is missing"
    )


def write_audit_log(
    username: str,
    question: str,
    tool_name: str | None,
    status: str,
    execution_time_ms: int | None = None,
    error_message: str | None = None,
):
    query = """
        INSERT INTO audit_logs (
            username,
            question,
            tool_name,
            status,
            execution_time_ms,
            error_message
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """

    with psycopg.connect(
        AUDIT_DATABASE_URL,
        connect_timeout=5,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                (
                    username,
                    question,
                    tool_name,
                    status,
                    execution_time_ms,
                    error_message,
                ),
            )

        connection.commit()


def list_audit_logs(
    *,
    username: str | None = None,
    status: str | None = None,
    tool_name: str | None = None,
    limit: int = 100,
) -> list[dict]:
    conditions: list[str] = []
    params: list[object] = []

    if username:
        conditions.append(
            "username ILIKE %s"
        )
        params.append(
            f"%{username.strip()}%"
        )

    if status:
        conditions.append(
            "status = %s"
        )
        params.append(
            status.strip()
        )

    if tool_name:
        conditions.append(
            "COALESCE(tool_name, '') ILIKE %s"
        )
        params.append(
            f"%{tool_name.strip()}%"
        )

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    safe_limit = max(
        1,
        min(int(limit), 200),
    )

    query = f"""
        SELECT
            username,
            question,
            tool_name,
            status,
            execution_time_ms,
            error_message,
            created_at
        FROM audit_logs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s
    """

    params.append(
        safe_limit
    )

    with psycopg.connect(
        AUDIT_READ_DATABASE_URL,
        connect_timeout=5,
    ) as connection:

        connection.execute(
            "SET statement_timeout = '5000ms'"
        )

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                tuple(params),
            )

            rows = cursor.fetchall()

    return [
        {
            "username": str(row[0]),
            "question": str(row[1]),
            "tool_name": (
                str(row[2])
                if row[2] is not None
                else None
            ),
            "status": str(row[3]),
            "execution_time_ms": (
                int(row[4])
                if row[4] is not None
                else None
            ),
            "error_message": (
                str(row[5])
                if row[5] is not None
                else None
            ),
            "created_at": row[6],
        }
        for row in rows
    ]

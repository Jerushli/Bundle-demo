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
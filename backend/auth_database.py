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

AUTH_DATABASE_URL = os.getenv(
    "AUTH_DATABASE_URL"
)

if not AUTH_DATABASE_URL:
    raise RuntimeError(
        "AUTH_DATABASE_URL is missing from the project .env file"
    )


def get_auth_database_connection():
    connection = psycopg.connect(
        AUTH_DATABASE_URL,
        connect_timeout=5,
    )

    connection.execute(
        "SET statement_timeout = '5000ms'"
    )

    connection.execute(
        "SET idle_in_transaction_session_timeout = '10000ms'"
    )

    return connection

import os

from pathlib import Path

import psycopg

from dotenv import load_dotenv


# Find the backend directory
BASE_DIR = Path(__file__).resolve().parent


# Load backend/.env explicitly
load_dotenv(BASE_DIR / ".env")


# Retrieve the Neon connection string
DATABASE_URL = os.getenv("DATABASE_URL")


def get_database_connection():
    connection = psycopg.connect(
        DATABASE_URL,
        connect_timeout=5,
    )

    # Stop SQL statements that run longer than 5 seconds.
    connection.execute(
        "SET statement_timeout = '5000ms'"
    )

    # Prevent abandoned transactions from remaining open.
    connection.execute(
        "SET idle_in_transaction_session_timeout = '10000ms'"
    )

    # Extra protection in addition to the bundle_reader DB role.
    connection.execute(
        "SET default_transaction_read_only = on"
    )

    return connection
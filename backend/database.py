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

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing. Check backend/.env"
        )

    return psycopg.connect(
        DATABASE_URL,
        connect_timeout=10
    )
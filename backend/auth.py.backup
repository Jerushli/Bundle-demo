import os
import hmac

from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)


APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET")


if not APP_USERNAME:
    raise RuntimeError(
        "APP_USERNAME is missing"
    )

if not APP_PASSWORD:
    raise RuntimeError(
        "APP_PASSWORD is missing"
    )

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is missing"
    )


JWT_ALGORITHM = "HS256"

JWT_EXPIRE_HOURS = 8


security = HTTPBearer(
    auto_error=False
)


def authenticate_user(
    username: str,
    password: str,
) -> bool:

    username_valid = hmac.compare_digest(
        username,
        APP_USERNAME,
    )

    password_valid = hmac.compare_digest(
        password,
        APP_PASSWORD,
    )

    return (
        username_valid
        and password_valid
    )


def create_access_token(
    username: str,
) -> str:

    now = datetime.now(
        timezone.utc
    )

    payload = {
        "sub": username,

        "iat": now,

        "exp": (
            now
            + timedelta(
                hours=JWT_EXPIRE_HOURS
            )
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def verify_access_token(
    credentials:
    HTTPAuthorizationCredentials
    | None = Depends(security),
) -> str:

    if credentials is None:

        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required."
            ),
        )

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[
                JWT_ALGORITHM
            ],
        )

    except jwt.ExpiredSignatureError:

        raise HTTPException(
            status_code=401,
            detail=(
                "Session expired. "
                "Please log in again."
            ),
        )

    except jwt.InvalidTokenError:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid authentication token."
            ),
        )

    username = payload.get("sub")

    if not username:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid authentication token."
            ),
        )

    return str(username)
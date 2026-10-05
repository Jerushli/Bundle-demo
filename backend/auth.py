import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal

import jwt

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from backend.auth_database import (
    get_auth_database_connection,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)


JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is missing"
    )


JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8

Role = Literal[
    "admin",
    "analyst",
    "viewer",
]


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: Role
    is_active: bool
    token_version: int


password_hasher = PasswordHasher()

security = HTTPBearer(
    auto_error=False
)


def normalize_username(
    username: str,
) -> str:
    return username.strip().lower()


def hash_password(
    password: str,
) -> str:
    return password_hasher.hash(
        password
    )


def get_user_by_username(
    username: str,
) -> AuthenticatedUser | None:
    normalized = normalize_username(
        username
    )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    is_active,
                    token_version
                FROM app.users
                WHERE lower(username) = %s
                LIMIT 1
                """,
                (normalized,),
            )

            row = cur.fetchone()

    if not row:
        return None

    return AuthenticatedUser(
        id=int(row[0]),
        username=str(row[1]),
        role=str(row[2]),  # type: ignore[arg-type]
        is_active=bool(row[3]),
        token_version=int(row[4]),
    )


def get_user_by_id(
    user_id: int,
) -> AuthenticatedUser | None:
    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    is_active,
                    token_version
                FROM app.users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            row = cur.fetchone()

    if not row:
        return None

    return AuthenticatedUser(
        id=int(row[0]),
        username=str(row[1]),
        role=str(row[2]),  # type: ignore[arg-type]
        is_active=bool(row[3]),
        token_version=int(row[4]),
    )


def authenticate_user(
    username: str,
    password: str,
) -> AuthenticatedUser | None:
    normalized = normalize_username(
        username
    )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    role,
                    is_active,
                    token_version
                FROM app.users
                WHERE lower(username) = %s
                LIMIT 1
                """,
                (normalized,),
            )

            row = cur.fetchone()

            if not row:
                return None

            (
                user_id,
                stored_username,
                password_hash,
                role,
                is_active,
                token_version,
            ) = row

            if not is_active:
                return None

            try:
                password_hasher.verify(
                    str(password_hash),
                    password,
                )
            except (
                VerifyMismatchError,
                VerificationError,
                InvalidHashError,
            ):
                return None

            if password_hasher.check_needs_rehash(
                str(password_hash)
            ):
                new_hash = hash_password(
                    password
                )

                cur.execute(
                    """
                    UPDATE app.users
                    SET
                        password_hash = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        new_hash,
                        user_id,
                    ),
                )

            cur.execute(
                """
                UPDATE app.users
                SET
                    last_login_at = now(),
                    updated_at = now()
                WHERE id = %s
                """,
                (user_id,),
            )

            conn.commit()

    return AuthenticatedUser(
        id=int(user_id),
        username=str(stored_username),
        role=str(role),  # type: ignore[arg-type]
        is_active=True,
        token_version=int(token_version),
    )


def create_access_token(
    user: AuthenticatedUser,
) -> str:
    now = datetime.now(
        timezone.utc
    )

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "ver": user.token_version,
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
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
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
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail=(
                "Session expired. "
                "Please log in again."
            ),
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid authentication token."
            ),
        ) from exc

    subject = payload.get("sub")

    try:
        user_id = int(subject)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid authentication token."
            ),
        ) from exc

    user = get_user_by_id(
        user_id
    )

    if (
        user is None
        or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "This account is unavailable."
            ),
        )

    token_version = payload.get("ver")

    if (
        not isinstance(token_version, int)
        or token_version != user.token_version
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "This session is no longer valid. "
                "Please log in again."
            ),
        )

    return user


def require_roles(
    *allowed_roles: Role,
) -> Callable[
    [AuthenticatedUser],
    AuthenticatedUser,
]:
    def dependency(
        current_user:
        AuthenticatedUser = Depends(
            verify_access_token
        ),
    ) -> AuthenticatedUser:
        if (
            current_user.role
            not in allowed_roles
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Your role does not have "
                    "permission for this action."
                ),
            )

        return current_user

    return dependency

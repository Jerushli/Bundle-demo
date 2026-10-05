from datetime import datetime

from backend.auth import (
    AuthenticatedUser,
    Role,
    hash_password,
    normalize_username,
)
from backend.auth_database import (
    get_auth_database_connection,
)


class UserManagementError(ValueError):
    pass


def list_users() -> list[dict]:
    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    is_active,
                    created_at,
                    updated_at,
                    last_login_at
                FROM app.users
                ORDER BY
                    lower(username),
                    id
                """
            )

            rows = cur.fetchall()

    return [
        {
            "id": int(row[0]),
            "username": str(row[1]),
            "role": str(row[2]),
            "is_active": bool(row[3]),
            "created_at": row[4],
            "updated_at": row[5],
            "last_login_at": row[6],
        }
        for row in rows
    ]


def create_user(
    *,
    username: str,
    password: str,
    role: Role,
) -> dict:
    clean_username = username.strip()

    if not clean_username:
        raise UserManagementError(
            "Username cannot be empty."
        )

    if len(clean_username) > 100:
        raise UserManagementError(
            "Username must be 100 characters or fewer."
        )

    if len(password) < 10:
        raise UserManagementError(
            "Password must contain at least 10 characters."
        )

    normalized = normalize_username(
        clean_username
    )

    password_hash = hash_password(
        password
    )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM app.users
                WHERE lower(username) = %s
                """,
                (normalized,),
            )

            if cur.fetchone():
                raise UserManagementError(
                    "That username already exists."
                )

            cur.execute(
                """
                INSERT INTO app.users (
                    username,
                    password_hash,
                    role,
                    is_active
                )
                VALUES (%s, %s, %s, true)
                RETURNING
                    id,
                    username,
                    role,
                    is_active,
                    created_at,
                    updated_at,
                    last_login_at
                """,
                (
                    clean_username,
                    password_hash,
                    role,
                ),
            )

            row = cur.fetchone()
            conn.commit()

    return {
        "id": int(row[0]),
        "username": str(row[1]),
        "role": str(row[2]),
        "is_active": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
        "last_login_at": row[6],
    }


def update_user_role(
    *,
    target_user_id: int,
    new_role: Role,
    acting_user: AuthenticatedUser,
) -> dict:
    if (
        target_user_id == acting_user.id
        and new_role != "admin"
    ):
        raise UserManagementError(
            "You cannot remove your own Admin role."
        )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    is_active
                FROM app.users
                WHERE id = %s
                FOR UPDATE
                """,
                (target_user_id,),
            )

            target = cur.fetchone()

            if not target:
                raise UserManagementError(
                    "User not found."
                )

            old_role = str(target[2])
            is_active = bool(target[3])

            if (
                old_role == "admin"
                and new_role != "admin"
                and is_active
            ):
                cur.execute(
                    """
                    SELECT count(*)
                    FROM app.users
                    WHERE
                        role = 'admin'
                        AND is_active = true
                    """
                )

                active_admins = int(
                    cur.fetchone()[0]
                )

                if active_admins <= 1:
                    raise UserManagementError(
                        "The last active Admin cannot be demoted."
                    )

            cur.execute(
                """
                UPDATE app.users
                SET
                    role = %s,
                    token_version = token_version + 1,
                    updated_at = now()
                WHERE id = %s
                RETURNING
                    id,
                    username,
                    role,
                    is_active,
                    created_at,
                    updated_at,
                    last_login_at
                """,
                (
                    new_role,
                    target_user_id,
                ),
            )

            row = cur.fetchone()
            conn.commit()

    return {
        "id": int(row[0]),
        "username": str(row[1]),
        "role": str(row[2]),
        "is_active": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
        "last_login_at": row[6],
    }


def update_user_active_status(
    *,
    target_user_id: int,
    is_active: bool,
    acting_user: AuthenticatedUser,
) -> dict:
    if (
        target_user_id == acting_user.id
        and not is_active
    ):
        raise UserManagementError(
            "You cannot deactivate your own account."
        )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    username,
                    role,
                    is_active
                FROM app.users
                WHERE id = %s
                FOR UPDATE
                """,
                (target_user_id,),
            )

            target = cur.fetchone()

            if not target:
                raise UserManagementError(
                    "User not found."
                )

            role = str(target[2])
            currently_active = bool(target[3])

            if (
                role == "admin"
                and currently_active
                and not is_active
            ):
                cur.execute(
                    """
                    SELECT count(*)
                    FROM app.users
                    WHERE
                        role = 'admin'
                        AND is_active = true
                    """
                )

                active_admins = int(
                    cur.fetchone()[0]
                )

                if active_admins <= 1:
                    raise UserManagementError(
                        "The last active Admin cannot be deactivated."
                    )

            cur.execute(
                """
                UPDATE app.users
                SET
                    is_active = %s,
                    token_version = token_version + 1,
                    updated_at = now()
                WHERE id = %s
                RETURNING
                    id,
                    username,
                    role,
                    is_active,
                    created_at,
                    updated_at,
                    last_login_at
                """,
                (
                    is_active,
                    target_user_id,
                ),
            )

            row = cur.fetchone()
            conn.commit()

    return {
        "id": int(row[0]),
        "username": str(row[1]),
        "role": str(row[2]),
        "is_active": bool(row[3]),
        "created_at": row[4],
        "updated_at": row[5],
        "last_login_at": row[6],
    }


def reset_user_password(
    *,
    target_user_id: int,
    new_password: str,
) -> None:
    if len(new_password) < 10:
        raise UserManagementError(
            "Password must contain at least 10 characters."
        )

    password_hash = hash_password(
        new_password
    )

    with get_auth_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app.users
                SET
                    password_hash = %s,
                    token_version = token_version + 1,
                    updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (
                    password_hash,
                    target_user_id,
                ),
            )

            if not cur.fetchone():
                raise UserManagementError(
                    "User not found."
                )

            conn.commit()

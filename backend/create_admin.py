import argparse
import getpass

from backend.auth import (
    hash_password,
    normalize_username,
)
from backend.auth_database import (
    get_auth_database_connection,
)


ALLOWED_ROLES = {
    "admin",
    "analyst",
    "viewer",
}


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a Bundle application user."
        )
    )

    parser.add_argument(
        "--username",
        required=True,
    )

    parser.add_argument(
        "--role",
        choices=sorted(
            ALLOWED_ROLES
        ),
        default="admin",
    )

    args = parser.parse_args()

    username = args.username.strip()

    if not username:
        raise SystemExit(
            "Username cannot be empty."
        )

    password = getpass.getpass(
        "Password: "
    )

    confirm = getpass.getpass(
        "Confirm password: "
    )

    if password != confirm:
        raise SystemExit(
            "Passwords do not match."
        )

    if len(password) < 10:
        raise SystemExit(
            "Use a password with at least 10 characters."
        )

    password_hash = hash_password(
        password
    )

    normalized = normalize_username(
        username
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
                raise SystemExit(
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
                RETURNING id
                """,
                (
                    username,
                    password_hash,
                    args.role,
                ),
            )

            user_id = cur.fetchone()[0]

            conn.commit()

    print(
        f"Created user {username!r} "
        f"with role {args.role!r} "
        f"(id={user_id})."
    )


if __name__ == "__main__":
    main()

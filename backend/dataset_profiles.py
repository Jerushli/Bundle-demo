import json
from typing import Any

from backend.dataset_registry import (
    get_active_dataset_name,
)
from backend.ingestion import (
    get_ingest_connection,
    sanitize_identifier,
)


def get_latest_business_profile(
    dataset_name: str | None = None,
) -> dict[str, Any]:
    clean_dataset = sanitize_identifier(
        dataset_name
        or get_active_dataset_name()
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT profile_json
                FROM analytics.dataset_business_profiles
                WHERE dataset_name = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (clean_dataset,),
            )

            row = cur.fetchone()

    if not row:
        raise ValueError(
            "No business profile exists for the active dataset. "
            "Run Bundle v2 Stage 5 first."
        )

    payload = row[0]

    if isinstance(
        payload,
        str,
    ):
        payload = json.loads(
            payload
        )

    profile = dict(
        payload
    )

    profile[
        "dataset_name"
    ] = clean_dataset

    return profile

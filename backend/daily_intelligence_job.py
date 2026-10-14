from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.daily_intelligence import (
    generate_daily_snapshot,
    get_active_dataset,
)
from backend.intelligence_change_detection import (
    detect_latest_changes,
)
from backend.daily_intelligence_evidence import (
    build_daily_evidence_package,
)
from backend.daily_intelligence_brief import (
    generate_daily_brief,
)
from backend.intelligence_alerts import (
    create_alerts_from_evidence,
)


VALID_ROLES = {
    "admin",
    "analyst",
    "viewer",
}


def _existing_successful_run(
    *,
    dataset_name: str,
    run_date: date,
    role_name: str,
) -> dict[str, Any] | None:
    query = """
        SELECT
            id AS run_id,
            dataset_name,
            run_date,
            role_name,
            status,
            snapshot_status,
            change_status,
            evidence_package_id,
            brief_id,
            alert_count,
            started_at,
            completed_at,
            error_message
        FROM bundle.intelligence_daily_runs
        WHERE dataset_name = %s
          AND run_date = %s
          AND role_name = %s
          AND status = 'completed'
        ORDER BY id DESC
        LIMIT 1
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    dataset_name,
                    run_date,
                    role_name,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row
        else None
    )


def _start_run(
    *,
    dataset_name: str,
    run_date: date,
    role_name: str,
) -> int:
    query = """
        INSERT INTO bundle.intelligence_daily_runs (
            dataset_name,
            run_date,
            role_name,
            status,
            started_at
        )
        VALUES (
            %s,
            %s,
            %s,
            'running',
            NOW()
        )
        RETURNING id
    """

    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    dataset_name,
                    run_date,
                    role_name,
                ),
            )

            run_id = cursor.fetchone()[0]

        connection.commit()

    return int(
        run_id
    )


def _finish_run(
    *,
    run_id: int,
    status: str,
    snapshot_status: str | None,
    change_status: str | None,
    evidence_package_id: int | None,
    brief_id: int | None,
    alert_count: int,
    error_message: str | None = None,
) -> None:
    query = """
        UPDATE bundle.intelligence_daily_runs
        SET
            status = %s,
            snapshot_status = %s,
            change_status = %s,
            evidence_package_id = %s,
            brief_id = %s,
            alert_count = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
    """

    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    status,
                    snapshot_status,
                    change_status,
                    evidence_package_id,
                    brief_id,
                    alert_count,
                    error_message,
                    run_id,
                ),
            )

        connection.commit()


def run_daily_intelligence(
    *,
    role_name: str = "admin",
    run_date: date | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if role_name not in VALID_ROLES:
        raise ValueError(
            "role_name must be one of: admin, analyst, viewer."
        )

    dataset = get_active_dataset()

    target_date = (
        run_date
        or date.today()
    )

    if not force:
        existing = _existing_successful_run(
            dataset_name=dataset.dataset_name,
            run_date=target_date,
            role_name=role_name,
        )

        if existing:
            return {
                "source": "daily_intelligence_job",
                "status": "skipped_already_completed",
                "dataset_name": dataset.dataset_name,
                "run_date": target_date.isoformat(),
                "role_name": role_name,
                "existing_run": existing,
            }

    run_id = _start_run(
        dataset_name=dataset.dataset_name,
        run_date=target_date,
        role_name=role_name,
    )

    snapshot_status = None
    change_status = None
    evidence_package_id = None
    brief_id = None
    alert_count = 0

    try:
        snapshot = generate_daily_snapshot(
            snapshot_date=target_date
        )

        snapshot_status = snapshot.get(
            "status"
        )

        changes = detect_latest_changes(
            persist=True
        )

        change_status = changes.get(
            "status"
        )

        evidence = build_daily_evidence_package(
            role=role_name,
            persist=True,
        )

        evidence_package_id = evidence.get(
            "package_id"
        )

        brief = generate_daily_brief(
            role=role_name,
            persist=True,
        )

        brief_id = brief.get(
            "brief_id"
        )

        alerts = create_alerts_from_evidence(
            evidence=evidence,
            role_name=role_name,
            run_id=run_id,
        )

        alert_count = alerts.get(
            "alert_count",
            0,
        )

        _finish_run(
            run_id=run_id,
            status="completed",
            snapshot_status=snapshot_status,
            change_status=change_status,
            evidence_package_id=evidence_package_id,
            brief_id=brief_id,
            alert_count=alert_count,
        )

        return {
            "source": "daily_intelligence_job",
            "status": "completed",
            "run_id": run_id,
            "dataset_name": dataset.dataset_name,
            "run_date": target_date.isoformat(),
            "role_name": role_name,
            "snapshot": snapshot,
            "changes": changes,
            "evidence_package_id": evidence_package_id,
            "brief_id": brief_id,
            "brief": brief,
            "alerts": alerts,
        }

    except Exception as exc:
        _finish_run(
            run_id=run_id,
            status="failed",
            snapshot_status=snapshot_status,
            change_status=change_status,
            evidence_package_id=evidence_package_id,
            brief_id=brief_id,
            alert_count=alert_count,
            error_message=(
                f"{type(exc).__name__}: "
                f"{str(exc)[:900]}"
            ),
        )

        raise


def list_daily_runs(
    *,
    limit: int = 30,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    safe_limit = max(
        1,
        min(
            int(limit),
            200,
        ),
    )

    query = """
        SELECT
            id AS run_id,
            dataset_name,
            run_date,
            role_name,
            status,
            snapshot_status,
            change_status,
            evidence_package_id,
            brief_id,
            alert_count,
            started_at,
            completed_at,
            error_message
        FROM bundle.intelligence_daily_runs
        WHERE dataset_name = %s
        ORDER BY
            run_date DESC,
            id DESC
        LIMIT %s
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    dataset.dataset_name,
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_job",
        "dataset_name": dataset.dataset_name,
        "runs": rows,
    }

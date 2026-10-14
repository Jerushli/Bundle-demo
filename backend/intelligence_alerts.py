from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.daily_intelligence import get_active_dataset


ALERT_SEVERITIES = {
    "warning",
    "critical",
}


def _fingerprint(
    *,
    dataset_name: str,
    alert_type: str,
    alert_key: str,
    evidence_date: str,
) -> str:
    raw = (
        f"{dataset_name}|"
        f"{alert_type}|"
        f"{alert_key}|"
        f"{evidence_date}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def create_alert(
    *,
    dataset_name: str,
    role_name: str,
    alert_type: str,
    alert_key: str,
    severity: str,
    title: str,
    message: str,
    evidence_date: date | None,
    evidence_payload: dict[str, Any],
    run_id: int | None,
) -> dict[str, Any]:
    if severity not in ALERT_SEVERITIES:
        raise ValueError(
            "Alert severity must be warning or critical."
        )

    if role_name not in {
        "admin",
        "analyst",
        "viewer",
    }:
        raise ValueError(
            "Invalid alert role."
        )

    fingerprint = _fingerprint(
        dataset_name=dataset_name,
        alert_type=alert_type,
        alert_key=alert_key,
        evidence_date=(
            evidence_date.isoformat()
            if evidence_date
            else "none"
        ),
    )

    query = """
        INSERT INTO bundle.intelligence_alerts (
            dataset_name,
            run_id,
            role_name,
            alert_type,
            alert_key,
            severity,
            title,
            message,
            evidence_date,
            evidence_payload,
            fingerprint,
            acknowledged,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s::jsonb,
            %s, FALSE, NOW()
        )
        ON CONFLICT (fingerprint)
        DO UPDATE SET
            run_id = EXCLUDED.run_id,
            severity = EXCLUDED.severity,
            title = EXCLUDED.title,
            message = EXCLUDED.message,
            evidence_payload = EXCLUDED.evidence_payload
        RETURNING
            id,
            dataset_name,
            run_id,
            role_name,
            alert_type,
            alert_key,
            severity,
            title,
            message,
            evidence_date,
            evidence_payload,
            fingerprint,
            acknowledged,
            acknowledged_at,
            acknowledged_by,
            created_at
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    dataset_name,
                    run_id,
                    role_name,
                    alert_type,
                    alert_key,
                    severity,
                    title,
                    message,
                    evidence_date,
                    json.dumps(
                        evidence_payload,
                        default=str,
                    ),
                    fingerprint,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(row)


def create_alerts_from_evidence(
    *,
    evidence: dict[str, Any],
    role_name: str,
    run_id: int | None,
) -> dict[str, Any]:
    dataset_name = (
        evidence
        .get(
            "dataset",
            {},
        )
        .get(
            "dataset_name"
        )
    )

    if not dataset_name:
        raise ValueError(
            "Evidence package is missing dataset_name."
        )

    evidence_date_raw = (
        evidence
        .get(
            "kpi_snapshot",
            {},
        )
        .get(
            "snapshot_date"
        )
    )

    evidence_date = None

    if evidence_date_raw:
        if isinstance(
            evidence_date_raw,
            date,
        ):
            evidence_date = evidence_date_raw
        else:
            evidence_date = date.fromisoformat(
                str(
                    evidence_date_raw
                )[:10]
            )

    created: list[
        dict[str, Any]
    ] = []

    changes = (
        evidence
        .get(
            "change_detection",
            {},
        )
        .get(
            "changes",
            [],
        )
    )

    for change in changes:
        severity = change.get(
            "severity"
        )

        if severity not in ALERT_SEVERITIES:
            continue

        kpi_key = change.get(
            "kpi_key",
            "unknown_kpi",
        )

        display_name = change.get(
            "display_name",
            kpi_key,
        )

        direction = change.get(
            "direction",
            "changed",
        )

        percent = change.get(
            "percentage_change"
        )

        if percent is None:
            change_text = (
                f"{display_name} has a "
                f"{severity} classified change."
            )
        else:
            change_text = (
                f"{display_name} shows a "
                f"{direction} of "
                f"{float(percent):.2f}% and is "
                f"classified as {severity}."
            )

        created.append(
            create_alert(
                dataset_name=dataset_name,
                role_name=role_name,
                alert_type="kpi_change",
                alert_key=kpi_key,
                severity=severity,
                title=(
                    f"{severity.title()} KPI change: "
                    f"{display_name}"
                ),
                message=change_text,
                evidence_date=evidence_date,
                evidence_payload=change,
                run_id=run_id,
            )
        )

    governance = evidence.get(
        "response_model_governance",
        {},
    )

    for warning in governance.get(
        "warnings",
        [],
    ):
        warning_type = warning.get(
            "type",
            "governance_warning",
        )

        model_id = warning.get(
            "model_id",
            "unknown",
        )

        severity = (
            "critical"
            if warning_type in {
                "expired",
                "not_validated",
            }
            else "warning"
        )

        created.append(
            create_alert(
                dataset_name=dataset_name,
                role_name=role_name,
                alert_type="model_governance",
                alert_key=(
                    f"{model_id}:"
                    f"{warning_type}"
                ),
                severity=severity,
                title=(
                    "Response-model governance "
                    f"{severity}"
                ),
                message=warning.get(
                    "message",
                    "Response-model governance requires review.",
                ),
                evidence_date=evidence_date,
                evidence_payload=warning,
                run_id=run_id,
            )
        )

    return {
        "source": "daily_intelligence_alerts",
        "dataset_name": dataset_name,
        "role_name": role_name,
        "alert_count": len(
            created
        ),
        "alerts": created,
    }


def list_alerts(
    *,
    role_name: str,
    limit: int = 100,
    severity: str | None = None,
    acknowledged: bool | None = None,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    if severity is not None:
        if severity not in ALERT_SEVERITIES:
            raise ValueError(
                "severity must be warning or critical."
            )

    query = """
        SELECT
            id AS alert_id,
            dataset_name,
            run_id,
            role_name,
            alert_type,
            alert_key,
            severity,
            title,
            message,
            evidence_date,
            evidence_payload,
            acknowledged,
            acknowledged_at,
            acknowledged_by,
            created_at
        FROM bundle.intelligence_alerts
        WHERE dataset_name = %s
          AND role_name = %s
    """

    params: list[
        Any
    ] = [
        dataset.dataset_name,
        role_name,
    ]

    if severity is not None:
        query += (
            " AND severity = %s"
        )
        params.append(
            severity
        )

    if acknowledged is not None:
        query += (
            " AND acknowledged = %s"
        )
        params.append(
            acknowledged
        )

    query += """
        ORDER BY
            acknowledged ASC,
            created_at DESC,
            id DESC
        LIMIT %s
    """

    params.append(
        safe_limit
    )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_alerts",
        "dataset_name": dataset.dataset_name,
        "role_name": role_name,
        "alerts": rows,
    }


def acknowledge_alert(
    *,
    alert_id: int,
    role_name: str,
    username: str,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    query = """
        UPDATE bundle.intelligence_alerts
        SET
            acknowledged = TRUE,
            acknowledged_at = NOW(),
            acknowledged_by = %s
        WHERE id = %s
          AND dataset_name = %s
          AND role_name = %s
        RETURNING
            id AS alert_id,
            dataset_name,
            run_id,
            role_name,
            alert_type,
            alert_key,
            severity,
            title,
            message,
            evidence_date,
            acknowledged,
            acknowledged_at,
            acknowledged_by,
            created_at
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    username,
                    alert_id,
                    dataset.dataset_name,
                    role_name,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise ValueError(
            "Alert not found for the current dataset and role."
        )

    return dict(row)

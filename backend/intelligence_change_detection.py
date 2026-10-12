from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.daily_intelligence import get_active_dataset


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def classify_percentage_change(
    percentage_change: Decimal | None,
    *,
    warning_change_percent: Decimal | None,
    critical_change_percent: Decimal | None,
) -> dict[str, Any]:
    """
    Deterministically classify an absolute percentage change.

    No thresholds are invented:
    - If no configured rule exists -> unclassified.
    - If percentage change is undefined (for example a zero baseline)
      -> unclassified.
    """
    if percentage_change is None:
        return {
            "severity": "unclassified",
            "classification_reason": "percentage_change_unavailable",
        }

    if (
        warning_change_percent is None
        or critical_change_percent is None
    ):
        return {
            "severity": "unclassified",
            "classification_reason": "no_configured_thresholds",
        }

    absolute_percent = abs(percentage_change)

    if absolute_percent >= critical_change_percent:
        return {
            "severity": "critical",
            "classification_reason": "critical_threshold_exceeded",
        }

    if absolute_percent >= warning_change_percent:
        return {
            "severity": "warning",
            "classification_reason": "warning_threshold_exceeded",
        }

    return {
        "severity": "normal",
        "classification_reason": "within_configured_thresholds",
    }


def upsert_change_rule(
    *,
    kpi_key: str,
    warning_change_percent: float,
    critical_change_percent: float,
    enabled: bool = True,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    warning = Decimal(str(warning_change_percent))
    critical = Decimal(str(critical_change_percent))

    if warning < 0:
        raise ValueError(
            "warning_change_percent must be greater than or equal to 0."
        )

    if critical <= 0:
        raise ValueError(
            "critical_change_percent must be greater than 0."
        )

    if critical < warning:
        raise ValueError(
            "critical_change_percent must be greater than or equal to "
            "warning_change_percent."
        )

    find_kpi = """
        SELECT
            id,
            kpi_key,
            display_name
        FROM bundle.intelligence_kpi_definitions
        WHERE dataset_name = %s
          AND kpi_key = %s
        LIMIT 1
    """

    upsert = """
        INSERT INTO bundle.intelligence_change_rules (
            dataset_name,
            kpi_definition_id,
            warning_change_percent,
            critical_change_percent,
            enabled,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (dataset_name, kpi_definition_id)
        DO UPDATE SET
            warning_change_percent = EXCLUDED.warning_change_percent,
            critical_change_percent = EXCLUDED.critical_change_percent,
            enabled = EXCLUDED.enabled,
            updated_at = NOW()
        RETURNING
            id,
            dataset_name,
            kpi_definition_id,
            warning_change_percent,
            critical_change_percent,
            enabled,
            created_at,
            updated_at
    """

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                find_kpi,
                (
                    dataset.dataset_name,
                    kpi_key,
                ),
            )
            kpi = cursor.fetchone()

            if kpi is None:
                raise ValueError(
                    f"KPI '{kpi_key}' does not exist for active dataset "
                    f"'{dataset.dataset_name}'."
                )

            cursor.execute(
                upsert,
                (
                    dataset.dataset_name,
                    kpi["id"],
                    warning,
                    critical,
                    enabled,
                ),
            )
            row = cursor.fetchone()

        connection.commit()

    return {
        **dict(row),
        "kpi_key": kpi["kpi_key"],
        "display_name": kpi["display_name"],
    }


def list_change_rules(
    *,
    include_disabled: bool = False,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    query = """
        SELECT
            r.id,
            r.dataset_name,
            r.kpi_definition_id,
            d.kpi_key,
            d.display_name,
            r.warning_change_percent,
            r.critical_change_percent,
            r.enabled,
            r.created_at,
            r.updated_at
        FROM bundle.intelligence_change_rules r
        JOIN bundle.intelligence_kpi_definitions d
          ON d.id = r.kpi_definition_id
        WHERE r.dataset_name = %s
    """

    params: list[Any] = [dataset.dataset_name]

    if not include_disabled:
        query += " AND r.enabled = TRUE"

    query += " ORDER BY d.id"

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_change_detection",
        "dataset_name": dataset.dataset_name,
        "rules": rows,
    }


def _direction(
    current_value: Decimal,
    previous_value: Decimal,
) -> str:
    if current_value > previous_value:
        return "increase"
    if current_value < previous_value:
        return "decrease"
    return "stable"


def _calculate_change(
    current_value: Decimal,
    previous_value: Decimal,
) -> tuple[Decimal, Decimal | None, str]:
    absolute_change = current_value - previous_value

    if previous_value == 0:
        percentage_change = (
            Decimal("0")
            if current_value == 0
            else None
        )
    else:
        percentage_change = (
            absolute_change
            / abs(previous_value)
            * Decimal("100")
        )

    return (
        absolute_change,
        percentage_change,
        _direction(
            current_value,
            previous_value,
        ),
    )


def detect_latest_changes(
    *,
    persist: bool = True,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    kpi_query = """
        SELECT
            d.id AS kpi_definition_id,
            d.kpi_key,
            d.display_name,
            d.enabled AS kpi_enabled,
            r.id AS rule_id,
            r.warning_change_percent,
            r.critical_change_percent,
            COALESCE(r.enabled, FALSE) AS rule_enabled
        FROM bundle.intelligence_kpi_definitions d
        LEFT JOIN bundle.intelligence_change_rules r
          ON r.dataset_name = d.dataset_name
         AND r.kpi_definition_id = d.id
        WHERE d.dataset_name = %s
          AND d.enabled = TRUE
        ORDER BY d.id
    """

    snapshot_query = """
        SELECT
            id,
            snapshot_date,
            metric_value,
            row_count,
            generated_at
        FROM bundle.intelligence_kpi_snapshots
        WHERE dataset_name = %s
          AND kpi_definition_id = %s
          AND status = 'success'
          AND metric_value IS NOT NULL
        ORDER BY
            snapshot_date DESC,
            generated_at DESC
        LIMIT 2
    """

    upsert_event = """
        INSERT INTO bundle.intelligence_change_events (
            dataset_name,
            kpi_definition_id,
            previous_snapshot_id,
            current_snapshot_id,
            previous_snapshot_date,
            current_snapshot_date,
            previous_value,
            current_value,
            absolute_change,
            percentage_change,
            direction,
            severity,
            classification_reason,
            detected_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            NOW()
        )
        ON CONFLICT (
            dataset_name,
            kpi_definition_id,
            current_snapshot_id
        )
        DO UPDATE SET
            previous_snapshot_id = EXCLUDED.previous_snapshot_id,
            previous_snapshot_date = EXCLUDED.previous_snapshot_date,
            current_snapshot_date = EXCLUDED.current_snapshot_date,
            previous_value = EXCLUDED.previous_value,
            current_value = EXCLUDED.current_value,
            absolute_change = EXCLUDED.absolute_change,
            percentage_change = EXCLUDED.percentage_change,
            direction = EXCLUDED.direction,
            severity = EXCLUDED.severity,
            classification_reason = EXCLUDED.classification_reason,
            detected_at = NOW()
        RETURNING id, detected_at
    """

    results: list[dict[str, Any]] = []

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                kpi_query,
                (dataset.dataset_name,),
            )
            kpis = cursor.fetchall()

            for kpi in kpis:
                cursor.execute(
                    snapshot_query,
                    (
                        dataset.dataset_name,
                        kpi["kpi_definition_id"],
                    ),
                )
                snapshots = cursor.fetchall()

                if len(snapshots) < 2:
                    results.append(
                        {
                            "kpi_definition_id": kpi["kpi_definition_id"],
                            "kpi_key": kpi["kpi_key"],
                            "display_name": kpi["display_name"],
                            "status": "insufficient_history",
                            "required_snapshots": 2,
                            "available_snapshots": len(snapshots),
                            "severity": "unclassified",
                        }
                    )
                    continue

                current = snapshots[0]
                previous = snapshots[1]

                current_value = _decimal(
                    current["metric_value"]
                )
                previous_value = _decimal(
                    previous["metric_value"]
                )

                if (
                    current_value is None
                    or previous_value is None
                ):
                    results.append(
                        {
                            "kpi_definition_id": kpi["kpi_definition_id"],
                            "kpi_key": kpi["kpi_key"],
                            "display_name": kpi["display_name"],
                            "status": "missing_metric_value",
                            "severity": "unclassified",
                        }
                    )
                    continue

                (
                    absolute_change,
                    percentage_change,
                    direction,
                ) = _calculate_change(
                    current_value,
                    previous_value,
                )

                rule_enabled = bool(
                    kpi["rule_enabled"]
                )

                classification = classify_percentage_change(
                    percentage_change,
                    warning_change_percent=(
                        _decimal(
                            kpi["warning_change_percent"]
                        )
                        if rule_enabled
                        else None
                    ),
                    critical_change_percent=(
                        _decimal(
                            kpi["critical_change_percent"]
                        )
                        if rule_enabled
                        else None
                    ),
                )

                event_id = None
                detected_at = None

                if persist:
                    cursor.execute(
                        upsert_event,
                        (
                            dataset.dataset_name,
                            kpi["kpi_definition_id"],
                            previous["id"],
                            current["id"],
                            previous["snapshot_date"],
                            current["snapshot_date"],
                            previous_value,
                            current_value,
                            absolute_change,
                            percentage_change,
                            direction,
                            classification["severity"],
                            classification[
                                "classification_reason"
                            ],
                        ),
                    )
                    stored = cursor.fetchone()
                    event_id = stored["id"]
                    detected_at = stored["detected_at"]

                results.append(
                    {
                        "event_id": event_id,
                        "kpi_definition_id": kpi["kpi_definition_id"],
                        "kpi_key": kpi["kpi_key"],
                        "display_name": kpi["display_name"],
                        "status": "evaluated",
                        "previous_snapshot_id": previous["id"],
                        "current_snapshot_id": current["id"],
                        "previous_snapshot_date": previous["snapshot_date"],
                        "current_snapshot_date": current["snapshot_date"],
                        "previous_value": previous_value,
                        "current_value": current_value,
                        "absolute_change": absolute_change,
                        "percentage_change": percentage_change,
                        "direction": direction,
                        "severity": classification["severity"],
                        "classification_reason": classification[
                            "classification_reason"
                        ],
                        "warning_change_percent": (
                            kpi["warning_change_percent"]
                            if rule_enabled
                            else None
                        ),
                        "critical_change_percent": (
                            kpi["critical_change_percent"]
                            if rule_enabled
                            else None
                        ),
                        "detected_at": detected_at,
                    }
                )

        if persist:
            connection.commit()

    severity_counts = {
        "critical": 0,
        "warning": 0,
        "normal": 0,
        "unclassified": 0,
    }

    for item in results:
        severity = item.get(
            "severity",
            "unclassified",
        )
        if severity in severity_counts:
            severity_counts[severity] += 1

    return {
        "source": "daily_intelligence_change_detection",
        "dataset_name": dataset.dataset_name,
        "status": "completed",
        "persisted": persist,
        "severity_counts": severity_counts,
        "changes": results,
    }


def get_change_events(
    *,
    limit: int = 100,
    severity: str | None = None,
) -> dict[str, Any]:
    dataset = get_active_dataset()

    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    allowed_severities = {
        "normal",
        "warning",
        "critical",
        "unclassified",
    }

    if (
        severity is not None
        and severity not in allowed_severities
    ):
        raise ValueError(
            "severity must be one of: normal, warning, critical, unclassified."
        )

    query = """
        SELECT
            e.id AS event_id,
            e.dataset_name,
            e.kpi_definition_id,
            d.kpi_key,
            d.display_name,
            e.previous_snapshot_id,
            e.current_snapshot_id,
            e.previous_snapshot_date,
            e.current_snapshot_date,
            e.previous_value,
            e.current_value,
            e.absolute_change,
            e.percentage_change,
            e.direction,
            e.severity,
            e.classification_reason,
            e.detected_at
        FROM bundle.intelligence_change_events e
        JOIN bundle.intelligence_kpi_definitions d
          ON d.id = e.kpi_definition_id
        WHERE e.dataset_name = %s
    """

    params: list[Any] = [
        dataset.dataset_name
    ]

    if severity is not None:
        query += " AND e.severity = %s"
        params.append(severity)

    query += """
        ORDER BY
            e.current_snapshot_date DESC,
            e.id DESC
        LIMIT %s
    """

    params.append(safe_limit)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                query,
                params,
            )
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_change_detection",
        "dataset_name": dataset.dataset_name,
        "events": rows,
    }

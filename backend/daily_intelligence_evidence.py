from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.daily_intelligence import get_active_dataset


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _table_exists(connection, schema_name: str, table_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = %s
            )
            """,
            (schema_name, table_name),
        )
        return bool(cursor.fetchone()[0])


def _table_columns(connection, schema_name: str, table_name: str) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema_name, table_name),
        )
        return {row[0] for row in cursor.fetchall()}


def _latest_snapshot_date(connection, dataset_name: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MAX(snapshot_date)
            FROM bundle.intelligence_kpi_snapshots
            WHERE dataset_name = %s
              AND status = 'success'
            """,
            (dataset_name,),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _latest_kpi_snapshot_section(connection, dataset_name: str, snapshot_date):
    if snapshot_date is None:
        return {
            "status": "unavailable",
            "reason": "no_successful_kpi_snapshots",
            "snapshot_date": None,
            "kpis": [],
        }

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                s.id AS snapshot_id,
                s.snapshot_date,
                s.metric_value,
                s.row_count,
                s.generated_at,
                d.id AS kpi_definition_id,
                d.kpi_key,
                d.display_name,
                d.column_name,
                d.aggregation
            FROM bundle.intelligence_kpi_snapshots s
            JOIN bundle.intelligence_kpi_definitions d
              ON d.id = s.kpi_definition_id
            WHERE s.dataset_name = %s
              AND s.snapshot_date = %s
              AND s.status = 'success'
            ORDER BY d.id
            """,
            (dataset_name, snapshot_date),
        )
        rows = cursor.fetchall()

    return {
        "status": "available" if rows else "unavailable",
        "snapshot_date": snapshot_date,
        "kpi_count": len(rows),
        "kpis": rows,
    }


def _latest_change_section(connection, dataset_name: str):
    if not _table_exists(
        connection, "bundle", "intelligence_change_events"
    ):
        return {
            "status": "unavailable",
            "reason": "stage_21_2_change_event_table_missing",
            "changes": [],
            "severity_counts": {},
        }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MAX(current_snapshot_date)
            FROM bundle.intelligence_change_events
            WHERE dataset_name = %s
            """,
            (dataset_name,),
        )
        row = cursor.fetchone()
        latest_date = row[0] if row else None

    if latest_date is None:
        return {
            "status": "unavailable",
            "reason": "no_change_events",
            "current_snapshot_date": None,
            "changes": [],
            "severity_counts": {},
        }

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                e.id AS event_id,
                e.kpi_definition_id,
                d.kpi_key,
                d.display_name,
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
              AND e.current_snapshot_date = %s
            ORDER BY d.id
            """,
            (dataset_name, latest_date),
        )
        rows = cursor.fetchall()

    severity_counts = {
        "critical": 0,
        "warning": 0,
        "normal": 0,
        "unclassified": 0,
    }
    for row in rows:
        sev = row["severity"]
        if sev in severity_counts:
            severity_counts[sev] += 1

    return {
        "status": "available",
        "current_snapshot_date": latest_date,
        "change_count": len(rows),
        "severity_counts": severity_counts,
        "changes": rows,
    }


def _response_model_governance_section(connection):
    if not _table_exists(connection, "bundle", "response_models"):
        return {
            "status": "unavailable",
            "reason": "bundle.response_models_table_missing",
            "models": [],
            "warnings": [],
        }

    columns = _table_columns(connection, "bundle", "response_models")
    desired = [
        "id",
        "model_id",
        "model_name",
        "input_variable",
        "output_variable",
        "scope_type",
        "scope_value",
        "validation_status",
        "min_input_change_percent",
        "max_input_change_percent",
        "validated_at",
        "max_age_days",
        "expires_at",
        "validation_methodology",
        "causal_evidence_level",
        "drift_status",
        "last_drift_check_at",
    ]
    selected = [c for c in desired if c in columns]

    if not selected:
        return {
            "status": "unavailable",
            "reason": "response_models_schema_not_recognized",
            "models": [],
            "warnings": [],
        }

    query = (
        "SELECT "
        + ", ".join(f'"{c}"' for c in selected)
        + " FROM bundle.response_models ORDER BY 1"
    )

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    today = datetime.now(timezone.utc).date()
    warnings = []

    for row in rows:
        model_ref = row.get("model_id") or row.get("id")

        if (
            "validation_status" in row
            and row.get("validation_status") != "validated"
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "not_validated",
                "message": "Response model is not currently validated.",
            })

        if (
            "drift_status" in row
            and row.get("drift_status") in {"warning", "failed", "not_checked"}
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "drift_status",
                "status": row.get("drift_status"),
                "message": "Response-model drift governance requires attention.",
            })

        expires_at = row.get("expires_at")
        if expires_at is not None:
            expiry_date = expires_at.date() if isinstance(expires_at, datetime) else expires_at
            if expiry_date < today:
                warnings.append({
                    "model_id": model_ref,
                    "type": "expired",
                    "message": "Response model governance expiry date has passed.",
                })

        if (
            "max_age_days" in row
            and row.get("max_age_days") is not None
            and row.get("validated_at") is None
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "missing_validation_date",
                "message": "Model has max_age_days configured but no validated_at.",
            })

        if (
            "min_input_change_percent" in row
            and "max_input_change_percent" in row
            and row.get("min_input_change_percent") is None
            and row.get("max_input_change_percent") is None
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "no_applicability_range",
                "message": "No response-model applicability range is configured.",
            })

        if (
            "validation_methodology" in row
            and row.get("validation_methodology") in {None, "", "unspecified"}
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "validation_methodology_unspecified",
                "message": "Response-model validation methodology is unspecified.",
            })

        if (
            "causal_evidence_level" in row
            and row.get("causal_evidence_level") in {None, "", "none", "associational"}
        ):
            warnings.append({
                "model_id": model_ref,
                "type": "causal_evidence_limited",
                "level": row.get("causal_evidence_level"),
                "message": "Model evidence should not be presented as proof of causality.",
            })

    return {
        "status": "available",
        "model_count": len(rows),
        "warning_count": len(warnings),
        "models": rows,
        "warnings": warnings,
    }


def _forecast_section():
    return {
        "status": "not_evaluated",
        "reason": "daily_forecast_comparison_not_persisted_for_stage_21_yet",
        "deviation_count": 0,
        "deviations": [],
    }


def _rag_section(role: str):
    return {
        "status": "deferred_secure_retrieval",
        "authorized_role": role,
        "reason": "secure_rag_context_is_attached_during_daily_brief_generation",
        "documents": [],
    }


def build_daily_evidence_package(*, role: str, persist: bool = True):
    if role not in {"admin", "analyst", "viewer"}:
        raise ValueError("role must be one of: admin, analyst, viewer.")

    dataset = get_active_dataset()

    with get_database_connection() as connection:
        snapshot_date = _latest_snapshot_date(connection, dataset.dataset_name)

        kpi_section = _latest_kpi_snapshot_section(
            connection, dataset.dataset_name, snapshot_date
        )
        change_section = _latest_change_section(
            connection, dataset.dataset_name
        )
        governance_section = _response_model_governance_section(connection)

        evidence = {
            "source": "daily_intelligence_evidence",
            "evidence_version": "21.3",
            "generated_at": datetime.now(timezone.utc),
            "dataset": {
                "dataset_name": dataset.dataset_name,
                "analytics_table": dataset.analytics_table,
            },
            "request_context": {"role": role},
            "kpi_snapshot": kpi_section,
            "change_detection": change_section,
            "forecast_deviation": _forecast_section(),
            "response_model_governance": governance_section,
            "rag_context": _rag_section(role),
            "guardrails": {
                "no_invented_causes": True,
                "no_arbitrary_sql": True,
                "no_autonomous_business_action": True,
                "no_unvalidated_response_model_use": True,
                "llm_numeric_calculation_allowed": False,
            },
        }

        sev = change_section.get("severity_counts", {})
        critical_changes = sev.get("critical", 0)
        warning_changes = sev.get("warning", 0)
        governance_warning_count = governance_section.get("warning_count", 0)

        evidence["summary"] = {
            "snapshot_available": kpi_section["status"] == "available",
            "change_evidence_available": change_section["status"] == "available",
            "critical_change_count": critical_changes,
            "warning_change_count": warning_changes,
            "governance_warning_count": governance_warning_count,
            "attention_required": (
                critical_changes > 0
                or warning_changes > 0
                or governance_warning_count > 0
            ),
        }

        package_id = None

        if persist:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO bundle.intelligence_evidence_packages (
                        dataset_name,
                        evidence_date,
                        role_name,
                        evidence_version,
                        evidence_json,
                        generated_at
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                    RETURNING id
                    """,
                    (
                        dataset.dataset_name,
                        snapshot_date,
                        role,
                        "21.3",
                        json.dumps(_json_safe(evidence)),
                    ),
                )
                package_id = cursor.fetchone()[0]
            connection.commit()

    evidence["package_id"] = package_id
    evidence["persisted"] = persist
    return _json_safe(evidence)


def get_evidence_packages(*, role: str, limit: int = 20):
    if role not in {"admin", "analyst", "viewer"}:
        raise ValueError("role must be one of: admin, analyst, viewer.")

    dataset = get_active_dataset()
    safe_limit = max(1, min(int(limit), 100))

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS package_id,
                    dataset_name,
                    evidence_date,
                    role_name,
                    evidence_version,
                    evidence_json,
                    generated_at
                FROM bundle.intelligence_evidence_packages
                WHERE dataset_name = %s
                  AND role_name = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (dataset.dataset_name, role, safe_limit),
            )
            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_evidence",
        "dataset_name": dataset.dataset_name,
        "role": role,
        "packages": _json_safe(rows),
    }

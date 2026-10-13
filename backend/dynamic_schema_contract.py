from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.text_structure_extractor import extract_structured_candidates


DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
)

BOOLEAN_VALUES = {
    "yes": True,
    "no": False,
    "true": True,
    "false": False,
    "1": True,
    "0": False,
}


def _parse_date(value: str) -> str | None:
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal | None:
    text = (
        value.strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("%", "")
    )
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _infer_field_contract(
    field_name: str,
    values: list[str],
    *,
    total_records: int,
) -> dict[str, Any]:
    clean = [str(v).strip() for v in values if str(v).strip()]
    present_count = len(clean)
    presence_ratio = present_count / total_records if total_records else 0.0

    if not clean:
        return {
            "field_name": field_name,
            "data_type": "text",
            "required": False,
            "allowed_values": None,
            "max_length": None,
            "observed_min": None,
            "observed_max": None,
            "presence_ratio": 0.0,
            "distinct_count": 0,
            "status": "proposed",
        }

    date_count = sum(1 for v in clean if _parse_date(v) is not None)
    numeric_values = [p for v in clean if (p := _parse_decimal(v)) is not None]
    boolean_count = sum(1 for v in clean if v.lower() in BOOLEAN_VALUES)
    distinct = sorted(set(clean))
    avg_length = sum(len(v) for v in clean) / len(clean)

    date_ratio = date_count / present_count
    numeric_ratio = len(numeric_values) / present_count
    boolean_ratio = boolean_count / present_count

    if date_ratio >= 0.95:
        data_type = "date"
    elif boolean_ratio >= 0.95:
        data_type = "boolean"
    elif numeric_ratio >= 0.95:
        integers_only = all(v == v.to_integral_value() for v in numeric_values)
        data_type = "integer" if integers_only else "decimal"
    elif len(distinct) <= 25 and avg_length <= 80:
        data_type = "categorical"
    elif avg_length >= 80:
        data_type = "text"
    else:
        data_type = "short_text"

    allowed_values = distinct if data_type in {"boolean", "categorical"} else None

    observed_min = None
    observed_max = None
    if data_type in {"integer", "decimal"} and numeric_values:
        observed_min = str(min(numeric_values))
        observed_max = str(max(numeric_values))

    return {
        "field_name": field_name,
        "data_type": data_type,
        "required": presence_ratio >= 0.999,
        "allowed_values": allowed_values,
        "max_length": (
            max(len(v) for v in clean)
            if data_type in {"text", "short_text", "categorical"}
            else None
        ),
        "observed_min": observed_min,
        "observed_max": observed_max,
        "presence_ratio": round(presence_ratio, 6),
        "distinct_count": len(distinct),
        "status": "proposed",
    }


def propose_schema_contract(
    extraction_result: dict[str, Any],
    *,
    dataset_name: str,
) -> dict[str, Any]:
    records = [
        r for r in extraction_result.get("records", [])
        if r.get("extraction_status") == "candidate_extracted"
    ]
    if not records:
        raise ValueError("No extracted candidate records are available.")

    values_by_field: dict[str, list[str]] = {}
    for record in records:
        for field_name, value in (record.get("fields", {}) or {}).items():
            values_by_field.setdefault(field_name, []).append(str(value))

    fields = [
        _infer_field_contract(
            name,
            values,
            total_records=len(records),
        )
        for name, values in sorted(values_by_field.items())
    ]

    return {
        "source": "dynamic_schema_contract",
        "contract_version": "22.4.1",
        "dataset_name": dataset_name,
        "status": "draft",
        "sample_record_count": len(records),
        "field_count": len(fields),
        "fields": fields,
        "guardrails": {
            "auto_approved": False,
            "observed_numeric_bounds_enforced": False,
            "unknown_fields_auto_trusted": False,
            "admin_approval_required": True,
        },
    }


def persist_schema_contract(
    proposal: dict[str, Any],
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO bundle.dataset_schema_contracts (
                    dataset_name, contract_version, status,
                    sample_record_count, field_count, proposal_json,
                    created_by, created_at
                )
                VALUES (%s, %s, 'draft', %s, %s, %s::jsonb, %s, NOW())
                RETURNING id AS contract_id, created_at
                """,
                (
                    proposal["dataset_name"],
                    proposal["contract_version"],
                    proposal["sample_record_count"],
                    proposal["field_count"],
                    json.dumps(proposal),
                    created_by,
                ),
            )
            row = cursor.fetchone()
            contract_id = row["contract_id"]

            for field in proposal["fields"]:
                cursor.execute(
                    """
                    INSERT INTO bundle.dataset_schema_contract_fields (
                        contract_id, field_name, data_type, required,
                        allowed_values, max_length,
                        observed_min, observed_max,
                        presence_ratio, distinct_count, created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s::jsonb, %s,
                        %s, %s, %s, %s, NOW()
                    )
                    """,
                    (
                        contract_id,
                        field["field_name"],
                        field["data_type"],
                        field["required"],
                        json.dumps(field["allowed_values"])
                        if field["allowed_values"] is not None else None,
                        field["max_length"],
                        field["observed_min"],
                        field["observed_max"],
                        field["presence_ratio"],
                        field["distinct_count"],
                    ),
                )
        connection.commit()

    return {
        **proposal,
        "contract_id": contract_id,
        "created_at": row["created_at"],
    }


def approve_schema_contract(
    contract_id: int,
    *,
    approved_by: str,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, dataset_name, status
                FROM bundle.dataset_schema_contracts
                WHERE id = %s
                FOR UPDATE
                """,
                (contract_id,),
            )
            contract = cursor.fetchone()

            if contract is None:
                raise ValueError("Schema contract not found.")
            if contract["status"] != "draft":
                raise ValueError("Only draft schema contracts can be approved.")

            cursor.execute(
                """
                UPDATE bundle.dataset_schema_contracts
                SET status = 'superseded'
                WHERE dataset_name = %s
                  AND status = 'approved'
                  AND id <> %s
                """,
                (contract["dataset_name"], contract_id),
            )

            cursor.execute(
                """
                UPDATE bundle.dataset_schema_contracts
                SET status = 'approved',
                    approved_by = %s,
                    approved_at = NOW()
                WHERE id = %s
                RETURNING id AS contract_id, dataset_name, status,
                          approved_by, approved_at
                """,
                (approved_by, contract_id),
            )
            result = cursor.fetchone()
        connection.commit()

    return dict(result)


def load_approved_contract(dataset_name: str) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id AS contract_id, dataset_name, contract_version,
                       status, approved_by, approved_at
                FROM bundle.dataset_schema_contracts
                WHERE dataset_name = %s
                  AND status = 'approved'
                ORDER BY approved_at DESC, id DESC
                LIMIT 1
                """,
                (dataset_name,),
            )
            contract = cursor.fetchone()
            if contract is None:
                raise ValueError(
                    f"No approved schema contract exists for '{dataset_name}'."
                )

            cursor.execute(
                """
                SELECT field_name, data_type, required, allowed_values,
                       max_length, observed_min, observed_max,
                       presence_ratio, distinct_count
                FROM bundle.dataset_schema_contract_fields
                WHERE contract_id = %s
                ORDER BY field_name
                """,
                (contract["contract_id"],),
            )
            fields = cursor.fetchall()

    return {**dict(contract), "fields": [dict(f) for f in fields]}


def _normalize_value(
    value: str,
    field: dict[str, Any],
) -> tuple[Any, str | None]:
    text = str(value).strip()
    data_type = field["data_type"]

    if data_type == "date":
        parsed = _parse_date(text)
        return (parsed, None) if parsed is not None else (None, "Invalid date value.")

    if data_type == "boolean":
        normalized = BOOLEAN_VALUES.get(text.lower())
        if normalized is None:
            return None, "Invalid boolean value."
        return ("Yes" if normalized else "No"), None

    if data_type in {"integer", "decimal"}:
        parsed = _parse_decimal(text)
        if parsed is None:
            return None, "Invalid numeric value."
        if data_type == "integer" and parsed != parsed.to_integral_value():
            return None, "Expected an integer value."
        return (int(parsed), None) if data_type == "integer" else (float(parsed), None)

    if field.get("max_length") is not None and len(text) > int(field["max_length"]):
        return None, "Text exceeds approved maximum length."

    allowed = field.get("allowed_values")
    if allowed is not None and text not in allowed:
        return None, "Value is outside the approved allowed values."

    return text, None


def validate_with_contract(
    extraction_result: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    field_map = {f["field_name"]: f for f in contract["fields"]}
    validated_records = []
    accepted = needs_review = rejected = 0

    for record in extraction_result.get("records", []):
        if record.get("extraction_status") != "candidate_extracted":
            validated_records.append({
                **record,
                "validation_status": "rejected",
                "warnings": [],
                "errors": ["Source record did not produce an extraction candidate."],
                "normalized_fields": {},
            })
            rejected += 1
            continue

        raw_fields = record.get("fields", {}) or {}
        warnings, errors = [], []
        normalized_fields = {}

        for field_name in raw_fields:
            if field_name not in field_map:
                warnings.append(
                    f"Unknown field '{field_name}' is not part "
                    "of the approved company schema contract."
                )

        for field_name, field in field_map.items():
            value = raw_fields.get(field_name)
            if value is None or str(value).strip() == "":
                if field["required"]:
                    errors.append(f"Required field '{field_name}' is missing.")
                continue

            normalized, error = _normalize_value(str(value), field)
            if error:
                errors.append(f"{field_name}: {error}")
            else:
                normalized_fields[field_name] = normalized

        if errors:
            status = "rejected"
            rejected += 1
        elif warnings:
            status = "needs_review"
            needs_review += 1
        else:
            status = "accepted"
            accepted += 1

        validated_records.append({
            "source_row_number": record.get("source_row_number"),
            "source_column": record.get("source_column"),
            "raw_text": record.get("raw_text"),
            "validation_status": status,
            "warnings": warnings,
            "errors": errors,
            "normalized_fields": normalized_fields,
        })

    return {
        "source": "dynamic_schema_validation",
        "validator_version": "22.4.1",
        "dataset_name": contract["dataset_name"],
        "contract_id": contract["contract_id"],
        "accepted_count": accepted,
        "needs_review_count": needs_review,
        "rejected_count": rejected,
        "record_count": len(validated_records),
        "records": validated_records,
        "status": "validated" if rejected == 0 else "validated_with_rejections",
        "guardrails": {
            "approved_contract_required": True,
            "unknown_fields_auto_trusted": False,
            "observed_numeric_bounds_auto_enforced": False,
            "llm_validation_used": False,
            "analytics_write_performed": False,
        },
        "next_stage": "22.5_confidence_and_human_review",
    }


def propose_contract_from_csv(
    file_path: str | Path,
    *,
    dataset_name: str,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
) -> dict[str, Any]:
    extraction = extract_structured_candidates(
        file_path,
        columns=columns,
        sample_rows=sample_rows,
    )
    return propose_schema_contract(extraction, dataset_name=dataset_name)


def validate_csv_with_approved_contract(
    file_path: str | Path,
    *,
    dataset_name: str,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
) -> dict[str, Any]:
    extraction = extract_structured_candidates(
        file_path,
        columns=columns,
        sample_rows=sample_rows,
    )
    contract = load_approved_contract(dataset_name)
    return validate_with_contract(extraction, contract)


def list_schema_contracts(
    *,
    dataset_name: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 200))
    query = """
        SELECT id AS contract_id, dataset_name, contract_version, status,
               sample_record_count, field_count, created_by, created_at,
               approved_by, approved_at
        FROM bundle.dataset_schema_contracts
    """
    params: list[Any] = []
    if dataset_name:
        query += " WHERE dataset_name = %s"
        params.append(dataset_name)
    query += " ORDER BY id DESC LIMIT %s"
    params.append(safe_limit)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return {"source": "dynamic_schema_contract", "contracts": rows}

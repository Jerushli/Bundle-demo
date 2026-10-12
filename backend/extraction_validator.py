from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.text_structure_extractor import extract_structured_candidates


SUPPORTED_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
)

DEFAULT_FIELD_RULES: dict[str, dict[str, Any]] = {
    "date": {
        "type": "date",
        "required": True,
    },
    "region": {
        "type": "text",
        "required": False,
        "max_length": 120,
    },
    "product": {
        "type": "text",
        "required": False,
        "max_length": 160,
    },
    "sales": {
        "type": "decimal",
        "required": False,
        "min_value": 0,
    },
    "profit": {
        "type": "decimal",
        "required": False,
    },
    "units": {
        "type": "integer",
        "required": False,
        "min_value": 0,
    },
    "customer": {
        "type": "text",
        "required": False,
        "max_length": 200,
    },
    "priority": {
        "type": "text",
        "required": False,
        "allowed_values": [
            "Low",
            "Medium",
            "High",
            "Critical",
        ],
    },
    "owner": {
        "type": "text",
        "required": False,
        "max_length": 160,
    },
    "issue": {
        "type": "text",
        "required": False,
        "max_length": 500,
    },
    "note": {
        "type": "text",
        "required": False,
        "max_length": 2000,
    },
}


def _clean_numeric_text(
    value: str,
) -> str:
    cleaned = value.strip()

    cleaned = re.sub(
        r"^[₹$€£]\s*",
        "",
        cleaned,
    )

    cleaned = cleaned.replace(
        ",",
        "",
    )

    cleaned = cleaned.rstrip(
        "%"
    ).strip()

    return cleaned


def _parse_decimal(
    value: str,
) -> Decimal:
    cleaned = _clean_numeric_text(
        value
    )

    try:
        return Decimal(
            cleaned
        )

    except InvalidOperation as exc:
        raise ValueError(
            f"'{value}' is not a valid decimal."
        ) from exc


def _parse_integer(
    value: str,
) -> int:
    decimal_value = _parse_decimal(
        value
    )

    if (
        decimal_value
        != decimal_value.to_integral()
    ):
        raise ValueError(
            f"'{value}' is not a whole number."
        )

    return int(
        decimal_value
    )


def _parse_date(
    value: str,
) -> str:
    clean = value.strip()

    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            parsed = datetime.strptime(
                clean,
                fmt,
            ).date()

            return parsed.isoformat()

        except ValueError:
            pass

    raise ValueError(
        f"'{value}' does not match a supported date format."
    )


def _validate_text(
    field_name: str,
    value: str,
    rule: dict[str, Any],
) -> str:
    clean = value.strip()

    max_length = rule.get(
        "max_length"
    )

    if (
        max_length is not None
        and len(
            clean
        )
        > int(
            max_length
        )
    ):
        raise ValueError(
            f"{field_name} exceeds max_length={max_length}."
        )

    allowed_values = rule.get(
        "allowed_values"
    )

    if (
        allowed_values
        is not None
        and clean not in allowed_values
    ):
        raise ValueError(
            f"{field_name} must be one of: "
            + ", ".join(
                allowed_values
            )
        )

    return clean


def _validate_value(
    field_name: str,
    raw_value: str,
    rule: dict[str, Any],
) -> Any:
    field_type = rule.get(
        "type",
        "text",
    )

    if field_type == "decimal":
        value = _parse_decimal(
            raw_value
        )

    elif field_type == "integer":
        value = _parse_integer(
            raw_value
        )

    elif field_type == "date":
        value = _parse_date(
            raw_value
        )

    elif field_type == "text":
        value = _validate_text(
            field_name,
            raw_value,
            rule,
        )

    else:
        raise ValueError(
            f"Unsupported validation type '{field_type}' "
            f"for field '{field_name}'."
        )

    if isinstance(
        value,
        Decimal,
    ):
        minimum = rule.get(
            "min_value"
        )

        maximum = rule.get(
            "max_value"
        )

        if (
            minimum is not None
            and value
            < Decimal(
                str(
                    minimum
                )
            )
        ):
            raise ValueError(
                f"{field_name} is below the minimum allowed value."
            )

        if (
            maximum is not None
            and value
            > Decimal(
                str(
                    maximum
                )
            )
        ):
            raise ValueError(
                f"{field_name} is above the maximum allowed value."
            )

    if isinstance(
        value,
        int,
    ):
        minimum = rule.get(
            "min_value"
        )

        maximum = rule.get(
            "max_value"
        )

        if (
            minimum is not None
            and value < int(
                minimum
            )
        ):
            raise ValueError(
                f"{field_name} is below the minimum allowed value."
            )

        if (
            maximum is not None
            and value > int(
                maximum
            )
        ):
            raise ValueError(
                f"{field_name} is above the maximum allowed value."
            )

    return value


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Decimal,
    ):
        return float(
            value
        )

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            key: _json_safe(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            _json_safe(
                item
            )
            for item in value
        ]

    return value


def validate_extracted_candidates(
    extraction_result: dict[str, Any],
    *,
    field_rules: dict[str, dict[str, Any]] | None = None,
    require_known_fields_only: bool = False,
) -> dict[str, Any]:
    rules = (
        field_rules
        if field_rules is not None
        else DEFAULT_FIELD_RULES
    )

    validated_records: list[
        dict[str, Any]
    ] = []

    accepted_count = 0
    rejected_count = 0
    review_count = 0

    for record in extraction_result.get(
        "records",
        [],
    ):
        raw_fields = record.get(
            "fields",
            {},
        )

        errors: list[str] = []
        warnings: list[str] = []
        normalized_fields: dict[
            str,
            Any,
        ] = {}

        for field_name, rule in rules.items():
            if (
                rule.get(
                    "required"
                )
                and not str(
                    raw_fields.get(
                        field_name,
                        ""
                    )
                ).strip()
            ):
                errors.append(
                    f"Required field '{field_name}' is missing."
                )

        for field_name, raw_value in raw_fields.items():
            if field_name not in rules:
                if require_known_fields_only:
                    errors.append(
                        f"Unknown field '{field_name}' is not allowed."
                    )
                else:
                    warnings.append(
                        f"Unknown field '{field_name}' was preserved as text "
                        "and requires review before analytics loading."
                    )

                    normalized_fields[
                        field_name
                    ] = str(
                        raw_value
                    ).strip()

                continue

            rule = rules[
                field_name
            ]

            clean_raw = str(
                raw_value
            ).strip()

            if not clean_raw:
                if rule.get(
                    "required"
                ):
                    errors.append(
                        f"Required field '{field_name}' is empty."
                    )

                continue

            try:
                normalized_fields[
                    field_name
                ] = _validate_value(
                    field_name,
                    clean_raw,
                    rule,
                )

            except ValueError as exc:
                errors.append(
                    str(
                        exc
                    )
                )

        duplicate_like_fields = [
            field
            for field in raw_fields
            if re.search(
                r"_\d+$",
                field,
            )
        ]

        if duplicate_like_fields:
            warnings.append(
                "Duplicate source keys were preserved with numeric suffixes: "
                + ", ".join(
                    duplicate_like_fields
                )
            )

        if errors:
            status = "rejected"
            rejected_count += 1

        elif warnings:
            status = "needs_review"
            review_count += 1

        else:
            status = "accepted"
            accepted_count += 1

        validated_records.append(
            {
                "source_row_number": record.get(
                    "source_row_number"
                ),
                "source_column": record.get(
                    "source_column"
                ),
                "raw_text": record.get(
                    "raw_text"
                ),
                "extraction_status": record.get(
                    "extraction_status"
                ),
                "validation_status": status,
                "raw_fields": raw_fields,
                "normalized_fields": _json_safe(
                    normalized_fields
                ),
                "errors": errors,
                "warnings": warnings,
            }
        )

    total = len(
        validated_records
    )

    accepted_ratio = (
        accepted_count
        / total
        if total
        else 0.0
    )

    overall_status = (
        "ready_for_review"
        if review_count > 0
        else (
            "ready_for_routing"
            if accepted_count > 0
            and rejected_count == 0
            else (
                "partially_valid"
                if accepted_count > 0
                else "invalid"
            )
        )
    )

    return {
        "source": "deterministic_extraction_validation",
        "validator_version": "22.4",
        "filename": extraction_result.get(
            "filename"
        ),
        "extractor_version": extraction_result.get(
            "extractor_version"
        ),
        "candidate_record_count": total,
        "accepted_count": accepted_count,
        "needs_review_count": review_count,
        "rejected_count": rejected_count,
        "accepted_ratio": round(
            accepted_ratio,
            4,
        ),
        "overall_status": overall_status,
        "field_rules": rules,
        "records": validated_records,
        "guardrails": {
            "analytics_write_performed": False,
            "unknown_fields_auto_trusted": False,
            "invalid_values_auto_coerced": False,
            "llm_validation_used": False,
        },
        "next_stage": (
            "22.5_confidence_and_human_review"
        ),
    }


def validate_csv_extraction(
    file_path: str | Path,
    *,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
    require_known_fields_only: bool = False,
) -> dict[str, Any]:
    extraction = extract_structured_candidates(
        file_path,
        columns=columns,
        sample_rows=sample_rows,
    )

    return validate_extracted_candidates(
        extraction,
        require_known_fields_only=require_known_fields_only,
    )


def persist_validation_run(
    result: dict[str, Any],
    *,
    dataset_name: str | None = None,
    extraction_run_id: int | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    query = """
        INSERT INTO bundle.extraction_validation_runs (
            dataset_name,
            extraction_run_id,
            filename,
            validator_version,
            candidate_record_count,
            accepted_count,
            needs_review_count,
            rejected_count,
            accepted_ratio,
            overall_status,
            result_json,
            created_by,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s::jsonb, %s, NOW()
        )
        RETURNING
            id AS validation_run_id,
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
                    extraction_run_id,
                    result.get(
                        "filename"
                    ),
                    result.get(
                        "validator_version"
                    ),
                    result.get(
                        "candidate_record_count"
                    ),
                    result.get(
                        "accepted_count"
                    ),
                    result.get(
                        "needs_review_count"
                    ),
                    result.get(
                        "rejected_count"
                    ),
                    result.get(
                        "accepted_ratio"
                    ),
                    result.get(
                        "overall_status"
                    ),
                    json.dumps(
                        result
                    ),
                    created_by,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return {
        **result,
        "validation_run_id": row[
            "validation_run_id"
        ],
        "persisted_at": row[
            "created_at"
        ],
    }


def list_validation_runs(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            200,
        ),
    )

    query = """
        SELECT
            id AS validation_run_id,
            dataset_name,
            extraction_run_id,
            filename,
            validator_version,
            candidate_record_count,
            accepted_count,
            needs_review_count,
            rejected_count,
            accepted_ratio,
            overall_status,
            result_json,
            created_by,
            created_at
        FROM bundle.extraction_validation_runs
        ORDER BY id DESC
        LIMIT %s
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "deterministic_extraction_validation",
        "runs": rows,
    }

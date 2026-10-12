from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.extraction_validator import validate_csv_extraction


CONFIDENCE_HIGH = 0.90
CONFIDENCE_REVIEW = 0.70


def _score_record(record: dict[str, Any]) -> dict[str, Any]:
    validation_status = record.get(
        "validation_status"
    )

    errors = record.get(
        "errors",
        [],
    )

    warnings = record.get(
        "warnings",
        [],
    )

    raw_fields = record.get(
        "raw_fields",
        {},
    )

    normalized_fields = record.get(
        "normalized_fields",
        {},
    )

    if validation_status == "rejected":
        return {
            "confidence": 0.0,
            "confidence_band": "blocked",
            "review_required": False,
            "routing_status": "blocked",
            "score_reasons": [
                "Deterministic validation rejected the record."
            ],
        }

    field_count = len(
        raw_fields
    )

    normalized_count = len(
        normalized_fields
    )

    if field_count == 0:
        completeness = 0.0
    else:
        completeness = (
            normalized_count
            / field_count
        )

    warning_penalty = min(
        0.20,
        0.05 * len(
            warnings
        ),
    )

    error_penalty = min(
        0.50,
        0.20 * len(
            errors
        ),
    )

    base = 0.95

    if validation_status == "needs_review":
        base = 0.78

    score = (
        base
        * completeness
        - warning_penalty
        - error_penalty
    )

    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    if score >= CONFIDENCE_HIGH and validation_status == "accepted":
        band = "high"
        review_required = False
        routing_status = "eligible_for_routing"

    elif score >= CONFIDENCE_REVIEW:
        band = "medium"
        review_required = True
        routing_status = "needs_human_review"

    else:
        band = "low"
        review_required = True
        routing_status = "needs_human_review"

    reasons: list[str] = []

    reasons.append(
        f"Validation status: {validation_status}."
    )

    reasons.append(
        f"Normalized field completeness: {completeness:.2f}."
    )

    if warnings:
        reasons.append(
            f"{len(warnings)} validation warning(s) reduced confidence."
        )

    if errors:
        reasons.append(
            f"{len(errors)} validation error(s) reduced confidence."
        )

    return {
        "confidence": round(
            score,
            4,
        ),
        "confidence_band": band,
        "review_required": review_required,
        "routing_status": routing_status,
        "score_reasons": reasons,
    }


def build_review_candidates(
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    scored_records: list[
        dict[str, Any]
    ] = []

    eligible_count = 0
    review_count = 0
    blocked_count = 0

    for record in validation_result.get(
        "records",
        [],
    ):
        score = _score_record(
            record
        )

        item = {
            **record,
            **score,
        }

        scored_records.append(
            item
        )

        routing_status = item[
            "routing_status"
        ]

        if routing_status == "eligible_for_routing":
            eligible_count += 1

        elif routing_status == "needs_human_review":
            review_count += 1

        elif routing_status == "blocked":
            blocked_count += 1

    return {
        "source": "confidence_review_routing",
        "review_version": "22.5",
        "filename": validation_result.get(
            "filename"
        ),
        "validation_run_summary": {
            "candidate_record_count": validation_result.get(
                "candidate_record_count",
                0,
            ),
            "accepted_count": validation_result.get(
                "accepted_count",
                0,
            ),
            "needs_review_count": validation_result.get(
                "needs_review_count",
                0,
            ),
            "rejected_count": validation_result.get(
                "rejected_count",
                0,
            ),
        },
        "eligible_for_routing_count": eligible_count,
        "human_review_count": review_count,
        "blocked_count": blocked_count,
        "records": scored_records,
        "thresholds": {
            "high_confidence": CONFIDENCE_HIGH,
            "review_floor": CONFIDENCE_REVIEW,
        },
        "guardrails": {
            "automatic_acceptance_requires_validation_accepted": True,
            "human_review_can_override_rejected": False,
            "analytics_write_performed": False,
            "llm_confidence_scoring_used": False,
        },
        "next_stage": (
            "22.6_structured_analytics_routing"
        ),
    }


def persist_review_batch(
    result: dict[str, Any],
    *,
    dataset_name: str | None = None,
    validation_run_id: int | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO bundle.normalization_review_batches (
                    dataset_name,
                    validation_run_id,
                    filename,
                    review_version,
                    eligible_for_routing_count,
                    human_review_count,
                    blocked_count,
                    result_json,
                    created_by,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s, NOW()
                )
                RETURNING
                    id AS review_batch_id,
                    created_at
                """,
                (
                    dataset_name,
                    validation_run_id,
                    result.get(
                        "filename"
                    ),
                    result.get(
                        "review_version"
                    ),
                    result.get(
                        "eligible_for_routing_count"
                    ),
                    result.get(
                        "human_review_count"
                    ),
                    result.get(
                        "blocked_count"
                    ),
                    json.dumps(
                        result
                    ),
                    created_by,
                ),
            )

            batch_row = cursor.fetchone()

            batch_id = batch_row[
                "review_batch_id"
            ]

            for record in result.get(
                "records",
                [],
            ):
                if (
                    record.get(
                        "routing_status"
                    )
                    != "needs_human_review"
                ):
                    continue

                cursor.execute(
                    """
                    INSERT INTO bundle.normalization_review_queue (
                        review_batch_id,
                        dataset_name,
                        source_row_number,
                        source_column,
                        raw_text,
                        candidate_fields,
                        normalized_fields,
                        validation_warnings,
                        validation_errors,
                        confidence,
                        confidence_band,
                        review_status,
                        created_by,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb,
                        %s::jsonb, %s::jsonb,
                        %s, %s, 'pending',
                        %s, NOW()
                    )
                    """,
                    (
                        batch_id,
                        dataset_name,
                        record.get(
                            "source_row_number"
                        ),
                        record.get(
                            "source_column"
                        ),
                        record.get(
                            "raw_text"
                        ),
                        json.dumps(
                            record.get(
                                "raw_fields",
                                {},
                            )
                        ),
                        json.dumps(
                            record.get(
                                "normalized_fields",
                                {},
                            )
                        ),
                        json.dumps(
                            record.get(
                                "warnings",
                                [],
                            )
                        ),
                        json.dumps(
                            record.get(
                                "errors",
                                [],
                            )
                        ),
                        record.get(
                            "confidence"
                        ),
                        record.get(
                            "confidence_band"
                        ),
                        created_by,
                    ),
                )

        connection.commit()

    return {
        **result,
        "review_batch_id": batch_id,
        "persisted_at": batch_row[
            "created_at"
        ],
    }


def list_review_queue(
    *,
    limit: int = 100,
    status: str | None = None,
) -> dict[str, Any]:
    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
    }

    if (
        status is not None
        and status not in allowed_statuses
    ):
        raise ValueError(
            "status must be pending, approved, or rejected."
        )

    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            500,
        ),
    )

    query = """
        SELECT
            id AS review_id,
            review_batch_id,
            dataset_name,
            source_row_number,
            source_column,
            raw_text,
            candidate_fields,
            normalized_fields,
            validation_warnings,
            validation_errors,
            confidence,
            confidence_band,
            review_status,
            reviewed_by,
            reviewed_at,
            reviewer_note,
            created_by,
            created_at
        FROM bundle.normalization_review_queue
    """

    params: list[
        Any
    ] = []

    if status is not None:
        query += (
            " WHERE review_status = %s"
        )

        params.append(
            status
        )

    query += """
        ORDER BY
            CASE review_status
                WHEN 'pending' THEN 0
                ELSE 1
            END,
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
        "source": "normalization_review_queue",
        "items": rows,
    }


def decide_review_item(
    *,
    review_id: int,
    decision: str,
    reviewer: str,
    reviewer_note: str | None = None,
) -> dict[str, Any]:
    if decision not in {
        "approved",
        "rejected",
    }:
        raise ValueError(
            "decision must be approved or rejected."
        )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    review_status
                FROM bundle.normalization_review_queue
                WHERE id = %s
                FOR UPDATE
                """,
                (
                    review_id,
                ),
            )

            current = cursor.fetchone()

            if current is None:
                raise ValueError(
                    "Review item not found."
                )

            if (
                current[
                    "review_status"
                ]
                != "pending"
            ):
                raise ValueError(
                    "Review item has already been decided."
                )

            cursor.execute(
                """
                UPDATE bundle.normalization_review_queue
                SET
                    review_status = %s,
                    reviewed_by = %s,
                    reviewed_at = NOW(),
                    reviewer_note = %s
                WHERE id = %s
                RETURNING
                    id AS review_id,
                    review_batch_id,
                    dataset_name,
                    source_row_number,
                    source_column,
                    candidate_fields,
                    normalized_fields,
                    confidence,
                    confidence_band,
                    review_status,
                    reviewed_by,
                    reviewed_at,
                    reviewer_note
                """,
                (
                    decision,
                    reviewer,
                    reviewer_note,
                    review_id,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return dict(
        row
    )


def run_confidence_review(
    file_path: str,
    *,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
    require_known_fields_only: bool = False,
) -> dict[str, Any]:
    validation = validate_csv_extraction(
        file_path,
        columns=columns,
        sample_rows=sample_rows,
        require_known_fields_only=require_known_fields_only,
    )

    return build_review_candidates(
        validation
    )

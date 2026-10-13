from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.input_file_classifier import classify_csv_file
from backend.mixed_content_detector import analyze_csv_columns
from backend.text_structure_extractor import extract_structured_candidates
from backend.extraction_validator import validate_extracted_candidates
from backend.normalization_review import build_review_candidates
from backend.structured_analytics_router import route_structured_to_analytics
from backend.unstructured_rag_router import (
    collect_rag_candidates,
    persist_rag_route,
)
from backend.normalization_lineage import (
    register_analytics_lineage,
    trace_source,
)


def _main_flow_summary(
    *,
    classification: dict[str, Any],
    column_analysis: dict[str, Any],
    extraction: dict[str, Any],
    validation: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    return {
        "classification": classification.get(
            "classification"
        ),
        "classification_route": classification.get(
            "recommended_route"
        ),
        "file_route": column_analysis.get(
            "routing",
            {},
        ).get(
            "file_route"
        ),
        "analytics_columns": column_analysis.get(
            "routing",
            {},
        ).get(
            "analytics_columns",
            [],
        ),
        "rag_columns": column_analysis.get(
            "routing",
            {},
        ).get(
            "rag_columns",
            [],
        ),
        "extraction_columns": column_analysis.get(
            "routing",
            {},
        ).get(
            "extraction_columns",
            [],
        ),
        "successful_extractions": extraction.get(
            "successful_extractions",
            0,
        ),
        "accepted_count": validation.get(
            "accepted_count",
            0,
        ),
        "needs_review_count": validation.get(
            "needs_review_count",
            0,
        ),
        "rejected_count": validation.get(
            "rejected_count",
            0,
        ),
        "eligible_for_routing_count": review.get(
            "eligible_for_routing_count",
            0,
        ),
        "human_review_count": review.get(
            "human_review_count",
            0,
        ),
        "blocked_count": review.get(
            "blocked_count",
            0,
        ),
    }


def run_company_onboarding_test(
    file_path: str | Path,
    *,
    dataset_name: str,
    access_level: str = "internal",
    sample_rows: int = 5000,
    persist_rag: bool = True,
    write_analytics: bool = True,
    created_by: str | None = None,
) -> dict[str, Any]:
    path = Path(
        file_path
    )

    classification = classify_csv_file(
        path,
        sample_rows=min(
            sample_rows,
            5000,
        ),
    )

    column_analysis = analyze_csv_columns(
        path,
        sample_rows=min(
            sample_rows,
            5000,
        ),
    )

    extraction = extract_structured_candidates(
        path,
        sample_rows=sample_rows,
    )

    validation = validate_extracted_candidates(
        extraction
    )

    review = build_review_candidates(
        validation
    )

    summary = _main_flow_summary(
        classification=classification,
        column_analysis=column_analysis,
        extraction=extraction,
        validation=validation,
        review=review,
    )

    analytics_result: dict[str, Any] | None = None
    analytics_lineage: dict[str, Any] | None = None

    if write_analytics:
        analytics_result = route_structured_to_analytics(
            path,
            dataset_name=dataset_name,
            sample_rows=sample_rows,
            created_by=created_by,
        )

        if analytics_result.get(
            "route_id"
        ):
            analytics_lineage = register_analytics_lineage(
                route_id=analytics_result[
                    "route_id"
                ],
                created_by=created_by,
            )

    rag_result = collect_rag_candidates(
        path,
        dataset_name=dataset_name,
        access_level=access_level,
        sample_rows=sample_rows,
        include_embedded_structure=False,
    )

    if persist_rag:
        rag_result = persist_rag_route(
            rag_result,
            created_by=created_by,
        )

    analytics_ok = (
        analytics_result is not None
        and analytics_result.get(
            "status"
        )
        in {
            "ready_for_onboarding",
            "nothing_routable",
        }
    )

    rag_ok = rag_result.get(
        "status"
    ) in {
        "rag_candidates_ready",
        "no_rag_candidates",
    }

    classification_ok = (
        classification.get(
            "classification"
        )
        in {
            "structured",
            "mixed",
            "unstructured",
        }
    )

    analysis_ok = bool(
        column_analysis.get(
            "columns"
        )
    )

    extraction_ok = (
        extraction.get(
            "successful_extractions",
            0,
        )
        > 0
    )

    validation_ok = (
        validation.get(
            "accepted_count",
            0,
        )
        > 0
    )

    review_ok = (
        review.get(
            "eligible_for_routing_count",
            0,
        )
        > 0
    )

    checks = {
        "classification_ok": classification_ok,
        "column_analysis_ok": analysis_ok,
        "structured_extraction_ok": extraction_ok,
        "deterministic_validation_ok": validation_ok,
        "confidence_routing_ok": review_ok,
        "analytics_staging_ok": analytics_ok,
        "rag_staging_ok": rag_ok,
        "analytics_lineage_ok": (
            analytics_lineage is not None
            and analytics_lineage.get(
                "registered_records",
                0,
            )
            >= 0
        )
        if write_analytics
        else True,
        "live_dataset_activation_attempted": False,
        "rag_vector_write_attempted_in_main_env": False,
    }

    required_checks = [
        key
        for key in checks
        if key.endswith(
            "_ok"
        )
    ]

    passed = all(
        bool(
            checks[
                key
            ]
        )
        for key in required_checks
    )

    result = {
        "source": "company_onboarding_test",
        "onboarding_version": "22.9",
        "dataset_name": dataset_name,
        "filename": path.name,
        "status": (
            "passed"
            if passed
            else "failed"
        ),
        "summary": summary,
        "checks": checks,
        "analytics": analytics_result,
        "analytics_lineage": analytics_lineage,
        "rag": {
            "rag_route_id": rag_result.get(
                "rag_route_id"
            ),
            "status": rag_result.get(
                "status"
            ),
            "selected_columns": rag_result.get(
                "selected_columns",
                [],
            ),
            "candidate_count": rag_result.get(
                "candidate_count",
                0,
            ),
            "access_level": rag_result.get(
                "access_level"
            ),
        },
        "guardrails": {
            "active_dataset_changed": False,
            "existing_live_table_replaced": False,
            "rag_embedding_performed_in_main_env": False,
            "llm_used_for_numeric_validation": False,
            "rejected_rows_loaded": False,
        },
        "next_action": (
            "stage_22_complete_after_final_checks_and_github_push"
            if passed
            else "fix_failed_check_before_completion"
        ),
    }

    return result


def persist_onboarding_test(
    result: dict[str, Any],
    *,
    created_by: str | None = None,
) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                INSERT INTO bundle.normalization_onboarding_runs (
                    dataset_name,
                    filename,
                    onboarding_version,
                    status,
                    summary_json,
                    checks_json,
                    result_json,
                    created_by,
                    created_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, NOW()
                )
                RETURNING
                    id AS onboarding_run_id,
                    created_at
                """,
                (
                    result[
                        "dataset_name"
                    ],
                    result[
                        "filename"
                    ],
                    result[
                        "onboarding_version"
                    ],
                    result[
                        "status"
                    ],
                    json.dumps(
                        result[
                            "summary"
                        ]
                    ),
                    json.dumps(
                        result[
                            "checks"
                        ]
                    ),
                    json.dumps(
                        result,
                        default=str,
                    ),
                    created_by,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return {
        **result,
        "onboarding_run_id": row[
            "onboarding_run_id"
        ],
        "persisted_at": row[
            "created_at"
        ],
    }


def list_onboarding_runs(
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

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS onboarding_run_id,
                    dataset_name,
                    filename,
                    onboarding_version,
                    status,
                    summary_json,
                    checks_json,
                    created_by,
                    created_at
                FROM bundle.normalization_onboarding_runs
                ORDER BY id DESC
                LIMIT %s
                """,
                (
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "company_onboarding_test",
        "runs": rows,
    }


def verify_lineage_sample(
    *,
    dataset_name: str,
    source_row_number: int = 1,
) -> dict[str, Any]:
    return trace_source(
        dataset_name=dataset_name,
        source_row_number=source_row_number,
        limit=100,
    )

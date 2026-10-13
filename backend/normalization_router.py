from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from pydantic import BaseModel, Field

from backend.auth import (
    AuthenticatedUser,
    require_roles,
)
from backend.input_file_classifier import (
    classify_csv_file,
    list_classifications,
    persist_classification,
)
from backend.mixed_content_detector import (
    analyze_csv_columns,
    list_column_analyses,
    persist_column_analysis,
)
from backend.text_structure_extractor import (
    extract_structured_candidates,
    list_extraction_runs,
    persist_extraction_run,
)
from backend.extraction_validator import (
    list_validation_runs,
    persist_validation_run,
    validate_csv_extraction,
)
from backend.normalization_review import (
    decide_review_item,
    list_review_queue,
    persist_review_batch,
    run_confidence_review,
)

from backend.unstructured_rag_router import (
    collect_rag_candidates,
    list_rag_queue,
    persist_rag_route,
)


from backend.normalization_lineage import (
    lineage_summary,
    register_analytics_lineage,
    trace_source,
    trace_target,
)

from backend.company_onboarding_test import (
    list_onboarding_runs,
    persist_onboarding_test,
    run_company_onboarding_test,
    verify_lineage_sample,
)

router = APIRouter()


MAX_NORMALIZATION_BYTES = int(
    os.getenv(
        "BUNDLE_CLASSIFIER_MAX_BYTES",
        str(
            100 * 1024 * 1024
        ),
    )
)


class ReviewDecisionRequest(BaseModel):
    decision: Literal[
        "approved",
        "rejected",
    ]

    reviewer_note: str | None = Field(
        default=None,
        max_length=1000,
    )


async def _save_request_csv(
    request: Request,
) -> tuple[
    Path,
    str,
]:
    filename = (
        request.headers.get(
            "X-Filename"
        )
        or "upload.csv"
    )

    if not filename.lower().endswith(
        ".csv"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Stage 22 currently supports CSV files only."
            ),
        )

    body = await request.body()

    if not body:
        raise HTTPException(
            status_code=400,
            detail="Uploaded CSV is empty.",
        )

    if len(body) > MAX_NORMALIZATION_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "File is larger than the Stage 22 normalization limit."
            ),
        )

    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".csv",
        delete=False,
    ) as temp:
        temp.write(
            body
        )

        path = Path(
            temp.name
        )

    return (
        path,
        filename,
    )


@router.post("/api/admin/normalization/classify")
async def classify_input_file(
    request: Request,
    dataset_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    sample_rows: int = Query(
        default=200,
        ge=10,
        le=5000,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = classify_csv_file(
            temporary_path,
            sample_rows=sample_rows,
        )

        result[
            "filename"
        ] = filename

        if persist:
            result = persist_classification(
                result,
                dataset_name=dataset_name,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/classifications")
def get_input_file_classifications(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return list_classifications(
        limit=limit
    )


@router.post("/api/admin/normalization/analyze-columns")
async def analyze_input_columns(
    request: Request,
    dataset_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    classification_id: int | None = Query(
        default=None,
        ge=1,
    ),
    sample_rows: int = Query(
        default=500,
        ge=10,
        le=5000,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = analyze_csv_columns(
            temporary_path,
            sample_rows=sample_rows,
        )

        result[
            "filename"
        ] = filename

        if persist:
            result = persist_column_analysis(
                result,
                dataset_name=dataset_name,
                classification_id=classification_id,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/column-analyses")
def get_column_analyses(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return list_column_analyses(
        limit=limit
    )


@router.post("/api/admin/normalization/extract-structured")
async def extract_structured_text(
    request: Request,
    dataset_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    analysis_id: int | None = Query(
        default=None,
        ge=1,
    ),
    column: list[str] | None = Query(
        default=None,
    ),
    sample_rows: int = Query(
        default=5000,
        ge=1,
        le=50000,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = extract_structured_candidates(
            temporary_path,
            columns=column,
            sample_rows=sample_rows,
        )

        result[
            "filename"
        ] = filename

        if persist:
            result = persist_extraction_run(
                result,
                dataset_name=dataset_name,
                analysis_id=analysis_id,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/extraction-runs")
def get_extraction_runs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return list_extraction_runs(
        limit=limit
    )


@router.post("/api/admin/normalization/validate-extraction")
async def validate_extraction(
    request: Request,
    dataset_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    extraction_run_id: int | None = Query(
        default=None,
        ge=1,
    ),
    column: list[str] | None = Query(
        default=None,
    ),
    sample_rows: int = Query(
        default=5000,
        ge=1,
        le=50000,
    ),
    require_known_fields_only: bool = Query(
        default=False,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = validate_csv_extraction(
            temporary_path,
            columns=column,
            sample_rows=sample_rows,
            require_known_fields_only=require_known_fields_only,
        )

        result[
            "filename"
        ] = filename

        if persist:
            result = persist_validation_run(
                result,
                dataset_name=dataset_name,
                extraction_run_id=extraction_run_id,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/validation-runs")
def get_validation_runs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return list_validation_runs(
        limit=limit
    )


# ==================================================
# STAGE 22.5 — CONFIDENCE + HUMAN REVIEW
# ==================================================

@router.post("/api/admin/normalization/prepare-review")
async def prepare_human_review(
    request: Request,
    dataset_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    validation_run_id: int | None = Query(
        default=None,
        ge=1,
    ),
    column: list[str] | None = Query(
        default=None,
    ),
    sample_rows: int = Query(
        default=5000,
        ge=1,
        le=50000,
    ),
    require_known_fields_only: bool = Query(
        default=False,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = run_confidence_review(
            str(
                temporary_path
            ),
            columns=column,
            sample_rows=sample_rows,
            require_known_fields_only=require_known_fields_only,
        )

        result[
            "filename"
        ] = filename

        if persist:
            result = persist_review_batch(
                result,
                dataset_name=dataset_name,
                validation_run_id=validation_run_id,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/review-queue")
def get_review_queue(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    status: Literal[
        "pending",
        "approved",
        "rejected",
    ] | None = None,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return list_review_queue(
            limit=limit,
            status=status,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@router.post(
    "/api/admin/normalization/review-queue/{review_id}/decision"
)
def decide_review(
    review_id: int,
    body: ReviewDecisionRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return decide_review_item(
            review_id=review_id,
            decision=body.decision,
            reviewer=current_user.username,
            reviewer_note=body.reviewer_note,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@router.post("/api/admin/normalization/route-rag")
async def route_unstructured_to_rag(
    request: Request,
    dataset_name: str = Query(
        min_length=1,
        max_length=100,
    ),
    access_level: Literal[
        "public",
        "internal",
        "restricted",
    ] = Query(default="internal"),
    sample_rows: int = Query(
        default=5000,
        ge=1,
        le=50000,
    ),
    include_embedded_structure: bool = Query(
        default=False,
    ),
    persist: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = collect_rag_candidates(
            temporary_path,
            dataset_name=dataset_name,
            access_level=access_level,
            sample_rows=sample_rows,
            include_embedded_structure=include_embedded_structure,
        )

        result["filename"] = filename

        if persist:
            result = persist_rag_route(
                result,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/rag-queue")
def get_rag_queue(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    status: Literal[
        "pending_export",
        "exported",
        "ingested",
        "failed",
    ] | None = None,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return list_rag_queue(
            limit=limit,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/normalization/lineage/register-analytics/{route_id}")
def register_structured_lineage(
    route_id: int,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    try:
        return register_analytics_lineage(
            route_id=route_id,
            created_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/admin/normalization/lineage/source")
def get_source_lineage(
    dataset_name: str = Query(min_length=1, max_length=100),
    source_row_number: int | None = Query(default=None, ge=1),
    source_column: str | None = Query(default=None, max_length=200),
    source_sha256: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    return trace_source(
        dataset_name=dataset_name,
        source_row_number=source_row_number,
        source_column=source_column,
        source_sha256=source_sha256,
        limit=limit,
    )


@router.get("/api/admin/normalization/lineage/target")
def get_target_lineage(
    target_system: Literal["analytics", "rag"],
    target_record_key: str | None = Query(default=None, max_length=200),
    target_locator: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    try:
        return trace_target(
            target_system=target_system,
            target_record_key=target_record_key,
            target_locator=target_locator,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/admin/normalization/lineage/summary")
def get_lineage_summary(
    dataset_name: str = Query(min_length=1, max_length=100),
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    return lineage_summary(dataset_name=dataset_name)


@router.post("/api/admin/normalization/onboarding-test")
async def run_onboarding_test_api(
    request: Request,
    dataset_name: str = Query(
        min_length=1,
        max_length=100,
    ),
    access_level: Literal[
        "public",
        "internal",
        "restricted",
    ] = Query(default="internal"),
    sample_rows: int = Query(
        default=5000,
        ge=1,
        le=50000,
    ),
    persist_run: bool = Query(
        default=True,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    temporary_path = None

    try:
        temporary_path, filename = await _save_request_csv(
            request
        )

        result = run_company_onboarding_test(
            temporary_path,
            dataset_name=dataset_name,
            access_level=access_level,
            sample_rows=sample_rows,
            persist_rag=True,
            write_analytics=True,
            created_by=current_user.username,
        )

        result["filename"] = filename

        if persist_run:
            result = persist_onboarding_test(
                result,
                created_by=current_user.username,
            )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(
                missing_ok=True
            )


@router.get("/api/admin/normalization/onboarding-runs")
def get_onboarding_runs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return list_onboarding_runs(
        limit=limit
    )


@router.get("/api/admin/normalization/onboarding-lineage-check")
def onboarding_lineage_check(
    dataset_name: str = Query(
        min_length=1,
        max_length=100,
    ),
    source_row_number: int = Query(
        default=1,
        ge=1,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    return verify_lineage_sample(
        dataset_name=dataset_name,
        source_row_number=source_row_number,
    )
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

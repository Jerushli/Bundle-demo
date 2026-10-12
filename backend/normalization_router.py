from __future__ import annotations
import os, tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend.auth import AuthenticatedUser, require_roles
from backend.input_file_classifier import classify_csv_file, list_classifications, persist_classification
from backend.mixed_content_detector import analyze_csv_columns, list_column_analyses, persist_column_analysis

router = APIRouter()
MAX_NORMALIZATION_BYTES = int(os.getenv("BUNDLE_CLASSIFIER_MAX_BYTES", str(100 * 1024 * 1024)))

async def _save_request_csv(request: Request) -> tuple[Path, str]:
    filename = request.headers.get("X-Filename") or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Stage 22 currently supports CSV files only.")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(body) > MAX_NORMALIZATION_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than the Stage 22 normalization limit.")
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as temp:
        temp.write(body)
        path = Path(temp.name)
    return path, filename

@router.post("/api/admin/normalization/classify")
async def classify_input_file(request: Request, dataset_name: str | None = Query(default=None, min_length=1, max_length=100), sample_rows: int = Query(default=200, ge=10, le=5000), persist: bool = Query(default=True), current_user: AuthenticatedUser = Depends(require_roles("admin"))):
    path = None
    try:
        path, filename = await _save_request_csv(request)
        result = classify_csv_file(path, sample_rows=sample_rows)
        result["filename"] = filename
        return persist_classification(result, dataset_name=dataset_name, created_by=current_user.username) if persist else result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if path and path.exists(): path.unlink(missing_ok=True)

@router.get("/api/admin/normalization/classifications")
def get_classifications(limit: int = Query(default=50, ge=1, le=200), current_user: AuthenticatedUser = Depends(require_roles("admin"))):
    return list_classifications(limit=limit)

@router.post("/api/admin/normalization/analyze-columns")
async def analyze_input_columns(request: Request, dataset_name: str | None = Query(default=None, min_length=1, max_length=100), classification_id: int | None = Query(default=None, ge=1), sample_rows: int = Query(default=500, ge=10, le=5000), persist: bool = Query(default=True), current_user: AuthenticatedUser = Depends(require_roles("admin"))):
    path = None
    try:
        path, filename = await _save_request_csv(request)
        result = analyze_csv_columns(path, sample_rows=sample_rows)
        result["filename"] = filename
        return persist_column_analysis(result, dataset_name=dataset_name, classification_id=classification_id, created_by=current_user.username) if persist else result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if path and path.exists(): path.unlink(missing_ok=True)

@router.get("/api/admin/normalization/column-analyses")
def get_column_analyses(limit: int = Query(default=50, ge=1, le=200), current_user: AuthenticatedUser = Depends(require_roles("admin"))):
    return list_column_analyses(limit=limit)

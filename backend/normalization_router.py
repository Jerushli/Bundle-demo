
from __future__ import annotations
import os, tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend.auth import AuthenticatedUser, require_roles
from backend.input_file_classifier import classify_csv_file, persist_classification, list_classifications

router=APIRouter()
MAX_CLASSIFY_BYTES=int(os.getenv("BUNDLE_CLASSIFIER_MAX_BYTES",str(100*1024*1024)))

@router.post("/api/admin/normalization/classify")
async def classify_input_file(
    request:Request,
    dataset_name:str|None=Query(default=None,min_length=1,max_length=100),
    sample_rows:int=Query(default=200,ge=10,le=5000),
    persist:bool=Query(default=True),
    current_user:AuthenticatedUser=Depends(require_roles("admin")),
):
    filename=request.headers.get("X-Filename") or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400,detail="Stage 22.1 currently supports CSV files only.")
    body=await request.body()
    if not body: raise HTTPException(status_code=400,detail="Uploaded CSV is empty.")
    if len(body)>MAX_CLASSIFY_BYTES:
        raise HTTPException(status_code=413,detail="File is larger than the Stage 22.1 classifier limit.")
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",suffix=".csv",delete=False) as temp:
            temp.write(body); temp_path=Path(temp.name)
        result=classify_csv_file(temp_path,sample_rows=sample_rows)
        result["filename"]=filename
        if persist:
            result=persist_classification(result,dataset_name=dataset_name,created_by=current_user.username)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    finally:
        if temp_path and temp_path.exists(): temp_path.unlink(missing_ok=True)

@router.get("/api/admin/normalization/classifications")
def classification_history(
    limit:int=Query(default=50,ge=1,le=200),
    current_user:AuthenticatedUser=Depends(require_roles("admin")),
):
    return list_classifications(limit=limit)

import logging
import os
import uuid

from pathlib import Path
from time import perf_counter
from datetime import datetime
from typing import Literal

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import (
    _rate_limit_exceeded_handler,
)
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.ai import process_chat
from backend.dataset_ai import process_dataset_chat
from backend.dataset_profiles import (
    get_active_dataset_name,
)
from backend.dataset_registry import (
    activate_dataset,
    dataset_to_dict,
    get_active_dataset,
    get_dataset,
    list_datasets,
    register_existing_dataset,
)
from backend.dataset_pipeline import (
    create_pipeline_job,
    get_pipeline_job,
    list_pipeline_jobs,
    run_dataset_pipeline,
    update_pipeline_job,
)
from backend.dataset_refresh import (
    run_dataset_refresh,
    technical_refresh_name,
)
from backend.ingestion import (
    sanitize_identifier,
)
from backend.rag_chat import process_rag_chat
from backend.hybrid_chat import process_hybrid_chat, should_use_hybrid
from backend.forecast_engine import (
    forecast_monthly_measure,
    forecast_to_dict,
    get_forecast_capabilities,
)
from backend.forecast_chat import (
    process_forecast_chat,
    should_use_forecast,
)
from backend.scenario_engine import (
    get_scenario_capabilities,
    scenario_to_dict,
    simulate_measure_percent_change,
)
from backend.scenario_chat import (
    process_scenario_chat,
    should_use_scenario,
)
from backend.decision_evidence import (
    build_decision_evidence,
    is_decision_question,
)
from backend.decision_chat import (
    process_decision_chat,
    should_use_decision,
)
from backend.investment_model import (
    calculate_investment_scenario,
    investment_result_to_dict,
)
from backend.investment_chat import (
    process_investment_chat,
    should_use_investment_scenario,
)
from backend.audit import (
    list_audit_logs,
    write_audit_log,
)

from backend.auth import (
    AuthenticatedUser,
    Role,
    authenticate_user,
    create_access_token,
    require_roles,
    verify_access_token,
)

from backend.admin_users import (
    UserManagementError,
    create_user,
    list_users,
    reset_user_password,
    update_user_active_status,
    update_user_role,
)


from backend.dataset_profiles import (
    get_latest_business_profile,
)


# ==================================================
# APPLICATION
# ==================================================

app = FastAPI(
    title="Bundle Data Assistant"
)

logger = logging.getLogger(__name__)


# ==================================================
# RATE LIMITING
# ==================================================

limiter = Limiter(
    key_func=get_remote_address
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.add_middleware(
    SlowAPIMiddleware
)


# ==================================================
# PATH CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_BUILD = (
    BASE_DIR
    / "frontend"
    / "build"
)


UPLOAD_ROOT = Path(
    os.getenv(
        "BUNDLE_UPLOAD_DIR",
        str(
            BASE_DIR
            / "data"
            / "uploads"
        ),
    )
).resolve()

MAX_UPLOAD_BYTES = int(
    os.getenv(
        "BUNDLE_MAX_UPLOAD_BYTES",
        str(
            10
            * 1024
            * 1024
            * 1024
        ),
    )
)

UPLOAD_CHUNK_BYTES = (
    8
    * 1024
    * 1024
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],

    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "OPTIONS",
    ],

    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)


# ==================================================
# REQUEST MODELS
# ==================================================

class LoginRequest(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100,
    )

    password: str = Field(
        min_length=1,
        max_length=200,
    )


class LoginResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    username: str

    role: Literal[
        "admin",
        "analyst",
        "viewer",
    ]


class CurrentUserResponse(BaseModel):

    id: int

    username: str

    role: Literal[
        "admin",
        "analyst",
        "viewer",
    ]


class ChatHistoryItem(BaseModel):

    role: Literal[
        "user",
        "assistant",
    ]

    content: str = Field(
        min_length=1,
        max_length=4000,
    )


class AnalysisContext(BaseModel):

    metric: str | None = None

    group_by: str | None = None

    entity: str | None = None

    year: int | None = None
    country: str | None = None
    product: str | None = None
    segment: str | None = None


class ChatRequest(BaseModel):

    message: str = Field(
        min_length=1,
        max_length=2000,
    )

    history: list[
        ChatHistoryItem
    ] = Field(
        default_factory=list,
        max_length=8,
    )

    context: AnalysisContext | None = None

    answer_mode: Literal[
        "summary",
        "detailed",
    ] = "summary"



class InvestmentScenarioRequest(BaseModel):

    target_column: str = Field(
        min_length=1,
        max_length=100,
    )

    target_value: str = Field(
        min_length=1,
        max_length=500,
    )

    investment_amount: float = Field(
        gt=0,
    )

    expected_revenue_uplift_percent: float = Field(
        ge=-100,
        le=500,
    )

    contribution_margin_percent: float = Field(
        ge=0,
        le=100,
    )

    horizon_months: int = Field(
        ge=1,
        le=120,
    )

    baseline_period_months: int = Field(
        ge=1,
        le=120,
    )

    hurdle_rate_percent: float = Field(
        ge=0,
        le=500,
    )

    max_payback_months: float = Field(
        gt=0,
        le=240,
    )

    baseline_measure: str = Field(
        default="sales",
        min_length=1,
        max_length=100,
    )




class DecisionEvidenceRequest(BaseModel):

    question: str = Field(
        min_length=3,
        max_length=2000,
    )




class ScenarioRequest(BaseModel):

    measure: str = Field(
        min_length=1,
        max_length=100,
    )

    change_percent: float = Field(
        ge=-500,
        le=500,
    )

    group_by: str | None = Field(
        default=None,
        max_length=100,
    )

    group_value: str | None = Field(
        default=None,
        max_length=500,
    )




class ForecastRequest(BaseModel):

    measure: str | None = Field(
        default=None,
        max_length=100,
    )

    date_column: str | None = Field(
        default=None,
        max_length=100,
    )

    horizon_months: int = Field(
        default=3,
        ge=1,
        le=12,
    )

    lookback_months: int = Field(
        default=24,
        ge=6,
        le=60,
    )




class RegisterDatasetRequest(BaseModel):

    dataset_name: str = Field(
        min_length=1,
        max_length=100,
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    source_type: str = Field(
        default="existing_postgresql",
        min_length=1,
        max_length=50,
    )

    source_name: str | None = Field(
        default=None,
        max_length=500,
    )

    analytics_table: str | None = Field(
        default=None,
        max_length=200,
    )

    status: Literal[
        "registered",
        "profiled",
        "validated",
        "ready",
        "failed",
    ] = "ready"

    row_count: int | None = Field(
        default=None,
        ge=0,
    )




class ManagedUserResponse(BaseModel):

    id: int

    username: str

    role: Literal[
        "admin",
        "analyst",
        "viewer",
    ]

    is_active: bool

    created_at: datetime

    updated_at: datetime

    last_login_at: datetime | None = None


class CreateUserRequest(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100,
    )

    password: str = Field(
        min_length=10,
        max_length=200,
    )

    role: Literal[
        "admin",
        "analyst",
        "viewer",
    ]


class UpdateUserRoleRequest(BaseModel):

    role: Literal[
        "admin",
        "analyst",
        "viewer",
    ]


class UpdateUserStatusRequest(BaseModel):

    is_active: bool


class ResetUserPasswordRequest(BaseModel):

    new_password: str = Field(
        min_length=10,
        max_length=200,
    )


class OperationMessageResponse(BaseModel):

    message: str


class AuditLogResponse(BaseModel):

    username: str

    question: str

    tool_name: str | None = None

    status: str

    execution_time_ms: int | None = None

    error_message: str | None = None

    created_at: datetime


# ==================================================
# AUDIT LOGGING
# ==================================================

def safe_write_audit_log(
    username: str,
    question: str,
    tool_name: str | None,
    status: str,
    execution_time_ms: int | None = None,
    error_message: str | None = None,
):

    try:

        write_audit_log(
            username=username,
            question=question,
            tool_name=tool_name,
            status=status,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
        )

    except Exception:

        logger.exception(
            "Failed to write audit log"
        )


# ==================================================
# LOGIN API
# ==================================================

@app.post(
    "/api/login",
    response_model=LoginResponse,
)
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
):

    user = authenticate_user(
        body.username,
        body.password,
    )

    if user is None:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid username or password."
            ),
        )

    token = create_access_token(
        user
    )

    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )


# ==================================================
# CURRENT USER API
# ==================================================

@app.get(
    "/api/me",
    response_model=CurrentUserResponse,
)
def me(
    current_user:
    AuthenticatedUser = Depends(
        verify_access_token
    ),
):

    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
    )



# ==================================================
# ADMIN USER MANAGEMENT API
# ==================================================

@app.get(
    "/api/admin/users",
    response_model=list[ManagedUserResponse],
)
def admin_list_users(
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    return list_users()


@app.post(
    "/api/admin/users",
    response_model=ManagedUserResponse,
    status_code=201,
)
def admin_create_user(
    body: CreateUserRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    try:

        return create_user(
            username=body.username,
            password=body.password,
            role=body.role,
        )

    except UserManagementError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.patch(
    "/api/admin/users/{user_id}/role",
    response_model=ManagedUserResponse,
)
def admin_update_user_role(
    user_id: int,
    body: UpdateUserRoleRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    try:

        return update_user_role(
            target_user_id=user_id,
            new_role=body.role,
            acting_user=current_user,
        )

    except UserManagementError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.patch(
    "/api/admin/users/{user_id}/status",
    response_model=ManagedUserResponse,
)
def admin_update_user_status(
    user_id: int,
    body: UpdateUserStatusRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    try:

        return update_user_active_status(
            target_user_id=user_id,
            is_active=body.is_active,
            acting_user=current_user,
        )

    except UserManagementError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/admin/users/{user_id}/reset-password",
    response_model=OperationMessageResponse,
)
def admin_reset_user_password(
    user_id: int,
    body: ResetUserPasswordRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    try:

        reset_user_password(
            target_user_id=user_id,
            new_password=body.new_password,
        )

    except UserManagementError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return OperationMessageResponse(
        message="Password reset successfully."
    )



# ==================================================
# ADMIN AUDIT API
# ==================================================

@app.get(
    "/api/admin/audit",
    response_model=list[AuditLogResponse],
)
def admin_list_audit_logs(
    username: str | None = Query(
        default=None,
        max_length=100,
    ),
    status: str | None = Query(
        default=None,
        max_length=50,
    ),
    tool: str | None = Query(
        default=None,
        max_length=100,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    current_user:
    AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):

    return list_audit_logs(
        username=username,
        status=status,
        tool_name=tool,
        limit=limit,
    )


# ==================================================
# DATASET REGISTRY API
# ==================================================

@app.get("/api/datasets")
def datasets_list(
    current_user:
    AuthenticatedUser = Depends(
        verify_access_token
    ),
):
    return [
        dataset_to_dict(
            item
        )
        for item in list_datasets()
    ]


@app.get("/api/datasets/active")
def active_dataset(
    current_user:
    AuthenticatedUser = Depends(
        verify_access_token
    ),
):
    try:
        return dataset_to_dict(
            get_active_dataset()
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/api/datasets/active/profile")
def active_dataset_profile(
    current_user:
    AuthenticatedUser = Depends(
        verify_access_token
    ),
):
    try:
        return get_latest_business_profile()

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/admin/datasets/register",
    status_code=201,
)
def admin_register_dataset(
    body: RegisterDatasetRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    try:
        record = register_existing_dataset(
            dataset_name=(
                body.dataset_name
            ),
            display_name=(
                body.display_name
            ),
            source_type=(
                body.source_type
            ),
            source_name=(
                body.source_name
            ),
            analytics_table=(
                body.analytics_table
            ),
            status=(
                body.status
            ),
            row_count=(
                body.row_count
            ),
        )

        return dataset_to_dict(
            record
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/admin/datasets/{dataset_name}/activate",
)
def admin_activate_dataset(
    dataset_name: str,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    try:
        record = activate_dataset(
            dataset_name
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Activate dataset: "
                f"{record.dataset_name}"
            ),
            tool_name=(
                "dataset_registry"
            ),
            status="success",
        )

        return dataset_to_dict(
            record
        )

    except ValueError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Activate dataset: "
                f"{dataset_name}"
            ),
            tool_name=(
                "dataset_registry"
            ),
            status="validation_error",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ==================================================
# DATASET UPLOAD + PIPELINE API
# ==================================================

@app.post(
    "/api/admin/datasets/upload",
    status_code=202,
)
async def admin_upload_dataset(
    background_tasks: BackgroundTasks,
    dataset_name: str = Form(...),
    display_name: str = Form(...),
    file: UploadFile = File(...),
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    clean_name = sanitize_identifier(
        dataset_name
    )

    if get_dataset(
        clean_name
    ) is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dataset {clean_name!r} already exists. "
                "Stage 12.2 only accepts new dataset names; "
                "daily refresh of an existing dataset comes in Stage 12.3."
            ),
        )

    original_filename = (
        Path(
            file.filename
            or "upload.csv"
        ).name
    )

    if (
        Path(
            original_filename
        ).suffix.lower()
        != ".csv"
    ):
        raise HTTPException(
            status_code=400,
            detail="Only CSV uploads are supported in Stage 12.2.",
        )

    try:
        register_existing_dataset(
            dataset_name=clean_name,
            display_name=display_name,
            source_type="csv_upload",
            source_name=original_filename,
            analytics_table=None,
            status="registered",
            row_count=None,
        )

        job_id = create_pipeline_job(
            dataset_name=clean_name,
            original_filename=(
                original_filename
            ),
        )

        dataset_dir = (
            UPLOAD_ROOT
            / clean_name
        )

        dataset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            dataset_dir
            / (
                f"{job_id}_"
                f"{uuid.uuid4().hex}.csv"
            )
        )

        total_bytes = 0

        try:
            with destination.open(
                "wb"
            ) as handle:
                while True:
                    chunk = await file.read(
                        UPLOAD_CHUNK_BYTES
                    )

                    if not chunk:
                        break

                    total_bytes += len(
                        chunk
                    )

                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise ValueError(
                            "Upload exceeds BUNDLE_MAX_UPLOAD_BYTES."
                        )

                    handle.write(
                        chunk
                    )

        finally:
            await file.close()

        if total_bytes == 0:
            raise ValueError(
                "Uploaded CSV is empty."
            )

        update_pipeline_job(
            job_id,
            status="queued",
            current_stage="queued",
            uploaded_path=str(
                destination
            ),
            error_message=None,
        )

        background_tasks.add_task(
            run_dataset_pipeline,
            job_id=job_id,
            dataset_name=clean_name,
            uploaded_path=str(
                destination
            ),
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Upload dataset: "
                f"{clean_name}"
            ),
            tool_name=(
                "dataset_pipeline"
            ),
            status="success",
        )

        return {
            "job_id": job_id,
            "dataset_name": clean_name,
            "display_name": display_name,
            "original_filename": (
                original_filename
            ),
            "uploaded_bytes": (
                total_bytes
            ),
            "status": "queued",
            "message": (
                "Upload completed. "
                "Dataset pipeline has been queued."
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        try:
            if (
                "job_id"
                in locals()
            ):
                update_pipeline_job(
                    job_id,
                    status="failed",
                    current_stage="failed",
                    error_message=(
                        f"{type(exc).__name__}: {exc}"
                    )[:2000],
                    finished=True,
                )
        except Exception:
            pass

        try:
            if (
                "destination"
                in locals()
                and destination.exists()
            ):
                destination.unlink()
        except Exception:
            pass

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc



@app.post(
    "/api/admin/datasets/{dataset_name}/refresh",
    status_code=202,
)
async def admin_refresh_dataset(
    dataset_name: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    clean_name = sanitize_identifier(
        dataset_name
    )

    record = get_dataset(
        clean_name
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Dataset {clean_name!r} is not registered."
            ),
        )

    if record.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dataset {clean_name!r} is not READY and "
                "cannot be refreshed safely."
            ),
        )

    original_filename = (
        Path(
            file.filename
            or "refresh.csv"
        ).name
    )

    if (
        Path(
            original_filename
        ).suffix.lower()
        != ".csv"
    ):
        raise HTTPException(
            status_code=400,
            detail="Only CSV refresh files are supported.",
        )

    destination = None
    job_id = None

    try:
        job_id = create_pipeline_job(
            dataset_name=clean_name,
            original_filename=(
                original_filename
            ),
            job_type="refresh",
        )

        technical_name = (
            technical_refresh_name(
                clean_name,
                job_id,
            )
        )

        dataset_dir = (
            UPLOAD_ROOT
            / clean_name
            / "refreshes"
        )

        dataset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            dataset_dir
            / (
                f"refresh_{job_id}_"
                f"{uuid.uuid4().hex}.csv"
            )
        )

        total_bytes = 0

        try:
            with destination.open(
                "wb"
            ) as handle:
                while True:
                    chunk = await file.read(
                        UPLOAD_CHUNK_BYTES
                    )

                    if not chunk:
                        break

                    total_bytes += len(
                        chunk
                    )

                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise ValueError(
                            "Upload exceeds BUNDLE_MAX_UPLOAD_BYTES."
                        )

                    handle.write(
                        chunk
                    )

        finally:
            await file.close()

        if total_bytes == 0:
            raise ValueError(
                "Refresh CSV is empty."
            )

        # Update path, technical identity, and queue state.
        from backend.ingestion import (
            get_ingest_connection,
        )

        with get_ingest_connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE bundle.pipeline_jobs
                    SET
                        uploaded_path = %s,
                        technical_dataset_name = %s,
                        status = 'queued',
                        current_stage = 'queued',
                        error_message = NULL,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        str(
                            destination
                        ),
                        technical_name,
                        job_id,
                    ),
                )

                connection.commit()

        background_tasks.add_task(
            run_dataset_refresh,
            job_id=job_id,
            dataset_name=clean_name,
            uploaded_path=str(
                destination
            ),
            original_filename=(
                original_filename
            ),
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Refresh dataset: "
                f"{clean_name}"
            ),
            tool_name=(
                "dataset_refresh"
            ),
            status="success",
        )

        return {
            "job_id": job_id,
            "job_type": "refresh",
            "dataset_name": clean_name,
            "technical_dataset_name": (
                technical_name
            ),
            "original_filename": (
                original_filename
            ),
            "uploaded_bytes": (
                total_bytes
            ),
            "status": "queued",
            "message": (
                "Refresh upload completed. "
                "A safe versioned refresh has been queued. "
                "The current live dataset remains available until promotion."
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        try:
            if job_id is not None:
                update_pipeline_job(
                    job_id,
                    status="failed",
                    current_stage="failed",
                    error_message=(
                        f"{type(exc).__name__}: {exc}"
                    )[:2000],
                    finished=True,
                )
        except Exception:
            pass

        try:
            if (
                destination is not None
                and destination.exists()
            ):
                destination.unlink()
        except Exception:
            pass

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@app.get(
    "/api/admin/dataset-jobs",
)
def admin_list_dataset_jobs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    return list_pipeline_jobs(
        limit=limit
    )


@app.get(
    "/api/admin/dataset-jobs/{job_id}",
)
def admin_get_dataset_job(
    job_id: int,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin"
        )
    ),
):
    job = get_pipeline_job(
        job_id
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Pipeline job {job_id} was not found."
            ),
        )

    return job


# ==================================================
# INVESTMENT MODEL API
# ==================================================

@app.post(
    "/api/investment/scenario",
)
def investment_scenario(
    body: InvestmentScenarioRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        result = calculate_investment_scenario(
            role=current_user.role,
            target_column=(
                body.target_column
            ),
            target_value=(
                body.target_value
            ),
            investment_amount=(
                body.investment_amount
            ),
            expected_revenue_uplift_percent=(
                body.expected_revenue_uplift_percent
            ),
            contribution_margin_percent=(
                body.contribution_margin_percent
            ),
            horizon_months=(
                body.horizon_months
            ),
            baseline_period_months=(
                body.baseline_period_months
            ),
            hurdle_rate_percent=(
                body.hurdle_rate_percent
            ),
            max_payback_months=(
                body.max_payback_months
            ),
            baseline_measure=(
                body.baseline_measure
            ),
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Investment scenario for "
                f"{result.target_column}={result.target_value}"
            ),
            tool_name=(
                "investment_model"
            ),
            status="success",
        )

        return investment_result_to_dict(
            result
        )

    except PermissionError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Investment scenario"
            ),
            tool_name=(
                "investment_model"
            ),
            status="forbidden",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Investment scenario"
            ),
            tool_name=(
                "investment_model"
            ),
            status="validation_error",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


# ==================================================
# DECISION EVIDENCE API
# ==================================================

@app.post(
    "/api/decision/evidence",
)
def decision_evidence(
    body: DecisionEvidenceRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        package = build_decision_evidence(
            question=body.question,
            role=current_user.role,
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                body.question
            ),
            tool_name=(
                "decision_evidence"
            ),
            status="success",
        )

        return package

    except PermissionError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                body.question
            ),
            tool_name=(
                "decision_evidence"
            ),
            status="forbidden",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                body.question
            ),
            tool_name=(
                "decision_evidence"
            ),
            status="validation_error",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


# ==================================================
# SCENARIO / WHAT-IF API
# ==================================================

@app.get(
    "/api/scenario/capabilities",
)
def scenario_capabilities(
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        return get_scenario_capabilities(
            role=current_user.role
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@app.post(
    "/api/scenario",
)
def create_scenario(
    body: ScenarioRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        result = simulate_measure_percent_change(
            role=current_user.role,
            measure=body.measure,
            change_percent=(
                body.change_percent
            ),
            group_by=body.group_by,
            group_value=(
                body.group_value
            ),
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Scenario "
                f"{result.measure} "
                f"{result.change_percent:+.2f}%"
            ),
            tool_name=(
                "scenario_engine"
            ),
            status="success",
        )

        return scenario_to_dict(
            result
        )

    except PermissionError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question="Scenario request",
            tool_name=(
                "scenario_engine"
            ),
            status="forbidden",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question="Scenario request",
            tool_name=(
                "scenario_engine"
            ),
            status="validation_error",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


# ==================================================
# FORECASTING API
# ==================================================

@app.get(
    "/api/forecast/capabilities",
)
def forecast_capabilities(
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        return get_forecast_capabilities(
            role=current_user.role
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@app.post(
    "/api/forecast",
)
def create_forecast(
    body: ForecastRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):
    try:
        result = forecast_monthly_measure(
            role=current_user.role,
            measure=body.measure,
            date_column=(
                body.date_column
            ),
            horizon_months=(
                body.horizon_months
            ),
            lookback_months=(
                body.lookback_months
            ),
        )

        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Forecast "
                f"{result.measure} "
                f"for {result.horizon_months} month(s)"
            ),
            tool_name=(
                "forecast_engine"
            ),
            status="success",
        )

        return forecast_to_dict(
            result
        )

    except PermissionError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Forecast request"
            ),
            tool_name=(
                "forecast_engine"
            ),
            status="forbidden",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        safe_write_audit_log(
            username=(
                current_user.username
            ),
            question=(
                "Forecast request"
            ),
            tool_name=(
                "forecast_engine"
            ),
            status="validation_error",
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


# ==================================================
# CHAT API
# ==================================================

@app.post("/api/chat")
@limiter.limit("30/minute")
def chat(
    request: Request,
    body: ChatRequest,
    current_user:
    AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
        )
    ),
):

    started_at = perf_counter()

    try:

        chat_history = [
            item.model_dump()
            for item in body.history
        ]

        chat_context = (
            body.context.model_dump()
            if body.context
            else None
        )

        # Bundle v2 structured analytics path.
        #
        # The active dataset is resolved from bundle.dataset_registry.
        #
        # Set BUNDLE_CHAT_MODE=legacy only when you intentionally want
        # to use the original fixed financial toolset.
        import os

        chat_mode = os.getenv(
            "BUNDLE_CHAT_MODE",
            "dataset",
        ).strip().lower()

        if chat_mode == "legacy":
            result = process_chat(
                body.message,
                history=chat_history,
                context=chat_context,
            )
        else:
            # This call also validates that an active dataset exists.
            get_active_dataset_name()

            dataset_name = get_active_dataset_name()

            if should_use_investment_scenario(
                question=body.message,
                role=current_user.role,
            ):
                result = process_investment_chat(
                    question=body.message,
                    role=current_user.role,
                    answer_mode=body.answer_mode,
                )

            elif should_use_decision(
                question=body.message,
                role=current_user.role,
            ):
                result = process_decision_chat(
                    question=body.message,
                    role=current_user.role,
                    answer_mode=body.answer_mode,
                )

            elif should_use_scenario(
                question=body.message,
                role=current_user.role,
            ):
                result = process_scenario_chat(
                    question=body.message,
                    role=current_user.role,
                    answer_mode=body.answer_mode,
                )

            elif should_use_forecast(
                question=body.message,
                role=current_user.role,
            ):
                result = process_forecast_chat(
                    question=body.message,
                    role=current_user.role,
                    answer_mode=body.answer_mode,
                )

            elif should_use_hybrid(
                question=body.message,
                role=current_user.role,
            ):
                result = process_hybrid_chat(
                    question=body.message,
                    role=current_user.role,
                    dataset_name=dataset_name,
                    answer_mode=body.answer_mode,
                )

            else:
                result = process_dataset_chat(
                    body.message,
                    history=chat_history,
                    context=chat_context,
                    answer_mode=body.answer_mode,
                    role=current_user.role,
                )

                if result.get(
                    "source"
                ) == "rag_required":
                    result = process_rag_chat(
                        question=body.message,
                        role=current_user.role,
                        dataset_name=dataset_name,
                        answer_mode=body.answer_mode,
                    )

        execution_time_ms = int(
            (
                perf_counter()
                - started_at
            )
            * 1000
        )

        tool_name = (
            result.get("tool_name")
            or result.get("source")
            or "no_tool"
        )

        safe_write_audit_log(
            username=current_user.username,
            question=body.message,
            tool_name=tool_name,
            status="success",
            execution_time_ms=(
                execution_time_ms
            ),
        )

        return result

    except ValueError as exc:

        execution_time_ms = int(
            (
                perf_counter()
                - started_at
            )
            * 1000
        )

        safe_write_audit_log(
            username=current_user.username,
            question=body.message,
            tool_name=None,
            status="validation_error",
            execution_time_ms=(
                execution_time_ms
            ),
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:

        execution_time_ms = int(
            (
                perf_counter()
                - started_at
            )
            * 1000
        )

        safe_write_audit_log(
            username=current_user.username,
            question=body.message,
            tool_name="dataset_security",
            status="forbidden",
            execution_time_ms=(
                execution_time_ms
            ),
            error_message=(
                str(exc)[:500]
            ),
        )

        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        execution_time_ms = int(
            (
                perf_counter()
                - started_at
            )
            * 1000
        )

        safe_write_audit_log(
            username=current_user.username,
            question=body.message,
            tool_name=None,
            status="error",
            execution_time_ms=(
                execution_time_ms
            ),
            error_message=(
                type(exc).__name__
            ),
        )

        logger.exception(
            "Chat request failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to process the request. "
                "Please try again."
            ),
        ) from exc


# ==================================================
# SERVE FRONTEND
# ==================================================

if FRONTEND_BUILD.exists():

    app.mount(
        "/_app",

        StaticFiles(
            directory=(
                FRONTEND_BUILD
                / "_app"
            )
        ),

        name="frontend-assets",
    )


    @app.get("/")
    def serve_frontend():

        return FileResponse(
            FRONTEND_BUILD
            / "index.html"
        )


    @app.get("/favicon.svg")
    def serve_favicon():

        return FileResponse(
            FRONTEND_BUILD
            / "favicon.svg"
        )


    @app.get("/robots.txt")
    def serve_robots():

        return FileResponse(
            FRONTEND_BUILD
            / "robots.txt"
        )

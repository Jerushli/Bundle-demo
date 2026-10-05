import logging

from pathlib import Path
from time import perf_counter
from datetime import datetime
from typing import Literal

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
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

        result = process_chat(
            body.message,

            history=[
                item.model_dump()
                for item in body.history
            ],

            context=(
                body.context.model_dump()
                if body.context
                else None
            ),
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

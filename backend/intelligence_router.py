from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedUser, require_roles
from backend.daily_intelligence import (
    create_kpi_definition,
    generate_daily_snapshot,
    get_available_columns,
    get_snapshots,
    list_kpi_definitions,
)
from backend.intelligence_change_detection import (
    detect_latest_changes,
    get_change_events,
    list_change_rules,
    upsert_change_rule,
)


router = APIRouter()


class KpiDefinitionRequest(BaseModel):
    kpi_key: str = Field(
        min_length=2,
        max_length=80,
    )
    display_name: str = Field(
        min_length=1,
        max_length=120,
    )
    column_name: str = Field(
        min_length=1,
        max_length=120,
    )
    aggregation: Literal[
        "sum",
        "avg",
        "count",
        "min",
        "max",
    ]
    enabled: bool = True


class SnapshotRequest(BaseModel):
    snapshot_date: date | None = None


class ChangeRuleRequest(BaseModel):
    kpi_key: str = Field(
        min_length=2,
        max_length=80,
    )
    warning_change_percent: float = Field(
        ge=0,
        le=1000000,
    )
    critical_change_percent: float = Field(
        gt=0,
        le=1000000,
    )
    enabled: bool = True


class DetectChangesRequest(BaseModel):
    persist: bool = True


@router.get("/api/intelligence/columns")
def intelligence_columns(
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
            "viewer",
        )
    ),
):
    try:
        return get_available_columns()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/api/intelligence/kpis")
def intelligence_kpis(
    include_disabled: bool = Query(False),
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
            "viewer",
        )
    ),
):
    try:
        return list_kpi_definitions(
            include_disabled=include_disabled
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/intelligence/kpis")
def admin_create_intelligence_kpi(
    body: KpiDefinitionRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return {
            "source": "daily_intelligence",
            "kpi": create_kpi_definition(
                kpi_key=body.kpi_key,
                display_name=body.display_name,
                column_name=body.column_name,
                aggregation=body.aggregation,
                enabled=body.enabled,
            ),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/intelligence/snapshot")
def admin_generate_intelligence_snapshot(
    body: SnapshotRequest | None = None,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return generate_daily_snapshot(
            snapshot_date=(
                body.snapshot_date
                if body is not None
                else None
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/api/intelligence/snapshots")
def intelligence_snapshots(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
            "viewer",
        )
    ),
):
    try:
        return get_snapshots(
            limit=limit
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ==================================================
# STAGE 21.2 — CHANGE / ANOMALY DETECTION
# ==================================================

@router.get("/api/intelligence/change-rules")
def intelligence_change_rules(
    include_disabled: bool = Query(False),
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
            "viewer",
        )
    ),
):
    try:
        return list_change_rules(
            include_disabled=include_disabled
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/intelligence/change-rules")
def admin_upsert_intelligence_change_rule(
    body: ChangeRuleRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return {
            "source": "daily_intelligence_change_detection",
            "rule": upsert_change_rule(
                kpi_key=body.kpi_key,
                warning_change_percent=body.warning_change_percent,
                critical_change_percent=body.critical_change_percent,
                enabled=body.enabled,
            ),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/admin/intelligence/detect-changes")
def admin_detect_intelligence_changes(
    body: DetectChangesRequest | None = None,
    current_user: AuthenticatedUser = Depends(
        require_roles("admin")
    ),
):
    try:
        return detect_latest_changes(
            persist=(
                body.persist
                if body is not None
                else True
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/api/intelligence/changes")
def intelligence_changes(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    severity: Literal[
        "normal",
        "warning",
        "critical",
        "unclassified",
    ] | None = None,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "admin",
            "analyst",
            "viewer",
        )
    ),
):
    try:
        return get_change_events(
            limit=limit,
            severity=severity,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

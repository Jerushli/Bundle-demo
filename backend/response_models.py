from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from backend.ingestion import get_ingest_connection


ModelType = Literal[
    "elasticity",
    "linear_percent",
]

ValidationStatus = Literal[
    "draft",
    "validated",
    "retired",
]

ConfidenceLevel = Literal[
    "low",
    "medium",
    "high",
]

ValidationMethodology = Literal[
    "unspecified",
    "holdout_validation",
    "time_series_backtest",
    "observational_statistical",
    "quasi_experimental",
    "randomized_experiment",
    "econometric_causal",
]

CausalEvidenceLevel = Literal[
    "none",
    "associational",
    "quasi_experimental",
    "experimental",
]

DriftStatus = Literal[
    "not_checked",
    "stable",
    "warning",
    "failed",
]


@dataclass(frozen=True)
class ResponseModel:
    id: int
    model_name: str
    input_variable: str
    output_variable: str
    scope_type: str | None
    scope_value: str | None
    model_type: str
    coefficient: float
    intercept: float
    training_start: Any
    training_end: Any
    sample_size: int | None
    validation_metric_name: str | None
    validation_metric_value: float | None
    confidence_level: str
    validation_status: str
    version: int
    notes: str
    created_by: str | None
    updated_by: str | None
    created_at: Any
    updated_at: Any
    min_input_change_percent: float | None
    max_input_change_percent: float | None
    validated_at: Any
    max_age_days: int | None
    expires_at: Any
    validation_methodology: str
    causal_evidence_level: str
    drift_status: str
    last_drift_check_at: Any


@dataclass(frozen=True)
class GovernanceAssessment:
    usable: bool
    blocking_reasons: list[str]
    warnings: list[str]
    applicability_within_range: bool | None
    freshness_status: str
    expiry_status: str
    drift_status: str


@dataclass(frozen=True)
class ResponseEstimate:
    model_id: int
    model_name: str
    version: int
    model_type: str
    input_variable: str
    output_variable: str
    scope_type: str | None
    scope_value: str | None
    input_change_percent: float
    estimated_output_change_percent: float
    coefficient: float
    intercept: float
    confidence_level: str
    validation_metric_name: str | None
    validation_metric_value: float | None
    training_start: Any
    training_end: Any
    sample_size: int | None
    min_input_change_percent: float | None
    max_input_change_percent: float | None
    validated_at: Any
    max_age_days: int | None
    expires_at: Any
    validation_methodology: str
    causal_evidence_level: str
    drift_status: str
    last_drift_check_at: Any
    governance_warnings: list[str]
    provenance: str
    limitations: list[str]


SELECT_COLUMNS = """
    id,
    model_name,
    input_variable,
    output_variable,
    scope_type,
    scope_value,
    model_type,
    coefficient,
    intercept,
    training_start,
    training_end,
    sample_size,
    validation_metric_name,
    validation_metric_value,
    confidence_level,
    validation_status,
    version,
    notes,
    created_by,
    updated_by,
    created_at,
    updated_at,
    min_input_change_percent,
    max_input_change_percent,
    validated_at,
    max_age_days,
    expires_at,
    validation_methodology,
    causal_evidence_level,
    drift_status,
    last_drift_check_at
"""


def _row_to_model(row) -> ResponseModel:
    return ResponseModel(
        id=int(row[0]),
        model_name=str(row[1]),
        input_variable=str(row[2]),
        output_variable=str(row[3]),
        scope_type=str(row[4]) if row[4] is not None else None,
        scope_value=str(row[5]) if row[5] is not None else None,
        model_type=str(row[6]),
        coefficient=float(row[7]),
        intercept=float(row[8]),
        training_start=row[9],
        training_end=row[10],
        sample_size=int(row[11]) if row[11] is not None else None,
        validation_metric_name=(
            str(row[12]) if row[12] is not None else None
        ),
        validation_metric_value=(
            float(row[13]) if row[13] is not None else None
        ),
        confidence_level=str(row[14]),
        validation_status=str(row[15]),
        version=int(row[16]),
        notes=str(row[17] or ""),
        created_by=str(row[18]) if row[18] is not None else None,
        updated_by=str(row[19]) if row[19] is not None else None,
        created_at=row[20],
        updated_at=row[21],
        min_input_change_percent=(
            float(row[22]) if row[22] is not None else None
        ),
        max_input_change_percent=(
            float(row[23]) if row[23] is not None else None
        ),
        validated_at=row[24],
        max_age_days=(
            int(row[25]) if row[25] is not None else None
        ),
        expires_at=row[26],
        validation_methodology=str(row[27] or "unspecified"),
        causal_evidence_level=str(row[28] or "associational"),
        drift_status=str(row[29] or "not_checked"),
        last_drift_check_at=row[30],
    )


def _validate_model_fields(
    *,
    model_type: str,
    confidence_level: str,
    validation_status: str,
    sample_size: int | None,
    version: int,
    min_input_change_percent: float | None = None,
    max_input_change_percent: float | None = None,
    max_age_days: int | None = None,
    validation_methodology: str = "unspecified",
    causal_evidence_level: str = "associational",
    drift_status: str = "not_checked",
):
    if model_type not in {
        "elasticity",
        "linear_percent",
    }:
        raise ValueError(
            "model_type must be 'elasticity' or 'linear_percent'."
        )

    if confidence_level not in {
        "low",
        "medium",
        "high",
    }:
        raise ValueError(
            "confidence_level must be low, medium, or high."
        )

    if validation_status not in {
        "draft",
        "validated",
        "retired",
    }:
        raise ValueError(
            "validation_status must be draft, validated, or retired."
        )

    if sample_size is not None and sample_size < 1:
        raise ValueError(
            "sample_size must be positive when supplied."
        )

    if version < 1:
        raise ValueError(
            "version must be at least 1."
        )

    if (
        min_input_change_percent is not None
        and max_input_change_percent is not None
        and min_input_change_percent > max_input_change_percent
    ):
        raise ValueError(
            "min_input_change_percent cannot exceed max_input_change_percent."
        )

    if max_age_days is not None and max_age_days < 1:
        raise ValueError(
            "max_age_days must be positive when supplied."
        )

    if validation_methodology not in {
        "unspecified",
        "holdout_validation",
        "time_series_backtest",
        "observational_statistical",
        "quasi_experimental",
        "randomized_experiment",
        "econometric_causal",
    }:
        raise ValueError(
            "Unsupported validation_methodology."
        )

    if causal_evidence_level not in {
        "none",
        "associational",
        "quasi_experimental",
        "experimental",
    }:
        raise ValueError(
            "Unsupported causal_evidence_level."
        )

    if drift_status not in {
        "not_checked",
        "stable",
        "warning",
        "failed",
    }:
        raise ValueError(
            "drift_status must be not_checked, stable, warning, or failed."
        )


def _as_date(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(
        str(value)
    )


def assess_model_governance(
    *,
    model: ResponseModel,
    input_change_percent: float,
    today: date | None = None,
) -> GovernanceAssessment:
    today = today or date.today()
    x = float(input_change_percent)

    blocking: list[str] = []
    warnings: list[str] = []

    within_range: bool | None = None

    if (
        model.min_input_change_percent is not None
        or model.max_input_change_percent is not None
    ):
        within_range = True

        if (
            model.min_input_change_percent is not None
            and x < model.min_input_change_percent
        ):
            within_range = False

        if (
            model.max_input_change_percent is not None
            and x > model.max_input_change_percent
        ):
            within_range = False

        if not within_range:
            blocking.append(
                "Requested input change is outside the model's approved "
                "applicability range."
            )
    else:
        warnings.append(
            "No explicit applicability range is configured for this model."
        )

    expiry_status = "not_configured"

    expires_at = _as_date(
        model.expires_at
    )

    if expires_at is not None:
        if today > expires_at:
            expiry_status = "expired"
            blocking.append(
                f"Model expired on {expires_at.isoformat()}."
            )
        else:
            expiry_status = "valid"

    freshness_status = "not_configured"

    validated_at = _as_date(
        model.validated_at
    )

    if (
        validated_at is not None
        and model.max_age_days is not None
    ):
        stale_after = (
            validated_at
            + timedelta(
                days=model.max_age_days
            )
        )

        if today > stale_after:
            freshness_status = "stale"
            blocking.append(
                "Model exceeded its configured maximum validation age "
                f"of {model.max_age_days} days."
            )
        else:
            freshness_status = "fresh"

    elif model.max_age_days is not None:
        freshness_status = "cannot_evaluate"
        blocking.append(
            "max_age_days is configured but validated_at is missing."
        )

    if model.drift_status == "failed":
        blocking.append(
            "Model drift status is failed."
        )

    elif model.drift_status == "warning":
        warnings.append(
            "Model drift status is warning; review before consequential use."
        )

    elif model.drift_status == "not_checked":
        warnings.append(
            "Model drift has not been checked."
        )

    if model.validation_methodology == "unspecified":
        warnings.append(
            "Validation methodology is unspecified."
        )

    if model.causal_evidence_level in {
        "none",
        "associational",
    }:
        warnings.append(
            "Model governance does not support a strong causal interpretation."
        )

    return GovernanceAssessment(
        usable=not blocking,
        blocking_reasons=blocking,
        warnings=warnings,
        applicability_within_range=within_range,
        freshness_status=freshness_status,
        expiry_status=expiry_status,
        drift_status=model.drift_status,
    )


def list_response_models(
    *,
    validation_status: str | None = None,
) -> list[ResponseModel]:
    query = f"""
        SELECT
            {SELECT_COLUMNS}
        FROM bundle.response_models
    """

    params: list[Any] = []

    if validation_status is not None:
        query += " WHERE validation_status = %s"
        params.append(validation_status)

    query += " ORDER BY model_name, version DESC"

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [
        _row_to_model(row)
        for row in rows
    ]


def get_response_model(
    model_id: int,
) -> ResponseModel | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    {SELECT_COLUMNS}
                FROM bundle.response_models
                WHERE id = %s
                LIMIT 1
                """,
                (int(model_id),),
            )
            row = cur.fetchone()

    return _row_to_model(row) if row else None


def create_response_model(
    *,
    model_name: str,
    input_variable: str,
    output_variable: str,
    scope_type: str | None,
    scope_value: str | None,
    model_type: str,
    coefficient: float,
    intercept: float,
    training_start,
    training_end,
    sample_size: int | None,
    validation_metric_name: str | None,
    validation_metric_value: float | None,
    confidence_level: str,
    validation_status: str,
    version: int,
    notes: str,
    created_by: str,
    min_input_change_percent: float | None = None,
    max_input_change_percent: float | None = None,
    validated_at=None,
    max_age_days: int | None = None,
    expires_at=None,
    validation_methodology: str = "unspecified",
    causal_evidence_level: str = "associational",
    drift_status: str = "not_checked",
    last_drift_check_at=None,
) -> ResponseModel:
    _validate_model_fields(
        model_type=model_type,
        confidence_level=confidence_level,
        validation_status=validation_status,
        sample_size=sample_size,
        version=version,
        min_input_change_percent=min_input_change_percent,
        max_input_change_percent=max_input_change_percent,
        max_age_days=max_age_days,
        validation_methodology=validation_methodology,
        causal_evidence_level=causal_evidence_level,
        drift_status=drift_status,
    )

    if not model_name.strip():
        raise ValueError(
            "model_name cannot be empty."
        )

    if not input_variable.strip():
        raise ValueError(
            "input_variable cannot be empty."
        )

    if not output_variable.strip():
        raise ValueError(
            "output_variable cannot be empty."
        )

    if (scope_type is None) != (scope_value is None):
        raise ValueError(
            "scope_type and scope_value must be supplied together."
        )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.response_models
                (
                    model_name,
                    input_variable,
                    output_variable,
                    scope_type,
                    scope_value,
                    model_type,
                    coefficient,
                    intercept,
                    training_start,
                    training_end,
                    sample_size,
                    validation_metric_name,
                    validation_metric_value,
                    confidence_level,
                    validation_status,
                    version,
                    notes,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at,
                    min_input_change_percent,
                    max_input_change_percent,
                    validated_at,
                    max_age_days,
                    expires_at,
                    validation_methodology,
                    causal_evidence_level,
                    drift_status,
                    last_drift_check_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, now(), now(),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    model_name.strip(),
                    input_variable.strip(),
                    output_variable.strip(),
                    scope_type.strip() if scope_type else None,
                    scope_value.strip() if scope_value else None,
                    model_type,
                    float(coefficient),
                    float(intercept),
                    training_start,
                    training_end,
                    sample_size,
                    validation_metric_name,
                    validation_metric_value,
                    confidence_level,
                    validation_status,
                    int(version),
                    notes or "",
                    created_by,
                    created_by,
                    min_input_change_percent,
                    max_input_change_percent,
                    validated_at,
                    max_age_days,
                    expires_at,
                    validation_methodology,
                    causal_evidence_level,
                    drift_status,
                    last_drift_check_at,
                ),
            )
            model_id = int(cur.fetchone()[0])
            connection.commit()

    created = get_response_model(model_id)

    if not created:
        raise RuntimeError(
            "Response model was created but could not be reloaded."
        )

    return created


def update_response_model_governance(
    *,
    model_id: int,
    min_input_change_percent: float | None,
    max_input_change_percent: float | None,
    validated_at,
    max_age_days: int | None,
    expires_at,
    validation_methodology: str,
    causal_evidence_level: str,
    drift_status: str,
    last_drift_check_at,
    updated_by: str,
) -> ResponseModel:
    existing = get_response_model(
        model_id
    )

    if not existing:
        raise ValueError(
            "Response model not found."
        )

    _validate_model_fields(
        model_type=existing.model_type,
        confidence_level=existing.confidence_level,
        validation_status=existing.validation_status,
        sample_size=existing.sample_size,
        version=existing.version,
        min_input_change_percent=min_input_change_percent,
        max_input_change_percent=max_input_change_percent,
        max_age_days=max_age_days,
        validation_methodology=validation_methodology,
        causal_evidence_level=causal_evidence_level,
        drift_status=drift_status,
    )

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE bundle.response_models
                SET
                    min_input_change_percent = %s,
                    max_input_change_percent = %s,
                    validated_at = %s,
                    max_age_days = %s,
                    expires_at = %s,
                    validation_methodology = %s,
                    causal_evidence_level = %s,
                    drift_status = %s,
                    last_drift_check_at = %s,
                    updated_by = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    min_input_change_percent,
                    max_input_change_percent,
                    validated_at,
                    max_age_days,
                    expires_at,
                    validation_methodology,
                    causal_evidence_level,
                    drift_status,
                    last_drift_check_at,
                    updated_by,
                    int(model_id),
                ),
            )
            connection.commit()

    updated = get_response_model(
        model_id
    )

    if not updated:
        raise RuntimeError(
            "Response model governance update could not be reloaded."
        )

    return updated


def find_validated_response_model(
    *,
    input_variable: str,
    output_variable: str,
    scope_type: str | None = None,
    scope_value: str | None = None,
) -> ResponseModel | None:
    """
    Deterministic resolution:
      1. exact validated scope
      2. validated company-wide model
    Highest version wins within the matching scope.

    Governance is evaluated after resolution so Bundle does not silently skip a
    blocked scoped model and substitute a broader company model.
    """
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            if scope_type and scope_value:
                cur.execute(
                    f"""
                    SELECT
                        {SELECT_COLUMNS}
                    FROM bundle.response_models
                    WHERE input_variable = %s
                      AND output_variable = %s
                      AND scope_type = %s
                      AND scope_value = %s
                      AND validation_status = 'validated'
                    ORDER BY version DESC, updated_at DESC
                    LIMIT 1
                    """,
                    (
                        input_variable,
                        output_variable,
                        scope_type,
                        scope_value,
                    ),
                )
                row = cur.fetchone()

                if row:
                    return _row_to_model(row)

            cur.execute(
                f"""
                SELECT
                    {SELECT_COLUMNS}
                FROM bundle.response_models
                WHERE input_variable = %s
                  AND output_variable = %s
                  AND scope_type IS NULL
                  AND scope_value IS NULL
                  AND validation_status = 'validated'
                ORDER BY version DESC, updated_at DESC
                LIMIT 1
                """,
                (
                    input_variable,
                    output_variable,
                ),
            )
            row = cur.fetchone()

    return _row_to_model(row) if row else None


def estimate_response(
    *,
    input_variable: str,
    output_variable: str,
    input_change_percent: float,
    scope_type: str | None = None,
    scope_value: str | None = None,
) -> ResponseEstimate:
    model = find_validated_response_model(
        input_variable=input_variable,
        output_variable=output_variable,
        scope_type=scope_type,
        scope_value=scope_value,
    )

    if not model:
        raise ValueError(
            "No validated response model is available for this relationship "
            "and scope. Supply an explicit scenario assumption instead."
        )

    x = float(
        input_change_percent
    )

    governance = assess_model_governance(
        model=model,
        input_change_percent=x,
    )

    if not governance.usable:
        raise ValueError(
            "Validated response model is blocked by governance: "
            + "; ".join(
                governance.blocking_reasons
            )
        )

    if model.model_type in {
        "elasticity",
        "linear_percent",
    }:
        estimated = (
            model.coefficient * x
            + model.intercept
        )

    else:
        raise ValueError(
            f"Unsupported validated model type: {model.model_type}"
        )

    limitations = [
        (
            "This estimate is produced from a registered validated response "
            "model; it is not generated by the LLM."
        ),
        (
            "The estimate is valid only to the extent that the model's training "
            "data, scope, assumptions, applicability range, freshness, and "
            "validation remain applicable."
        ),
        (
            "A validated response model does not by itself prove causality. "
            "Causal interpretation is limited by causal_evidence_level and "
            "validation_methodology."
        ),
        (
            "Management should review model provenance, confidence, drift, and "
            "governance warnings before consequential use."
        ),
    ]

    return ResponseEstimate(
        model_id=model.id,
        model_name=model.model_name,
        version=model.version,
        model_type=model.model_type,
        input_variable=model.input_variable,
        output_variable=model.output_variable,
        scope_type=model.scope_type,
        scope_value=model.scope_value,
        input_change_percent=round(x, 6),
        estimated_output_change_percent=round(
            estimated,
            6,
        ),
        coefficient=round(
            model.coefficient,
            8,
        ),
        intercept=round(
            model.intercept,
            8,
        ),
        confidence_level=model.confidence_level,
        validation_metric_name=model.validation_metric_name,
        validation_metric_value=model.validation_metric_value,
        training_start=model.training_start,
        training_end=model.training_end,
        sample_size=model.sample_size,
        min_input_change_percent=model.min_input_change_percent,
        max_input_change_percent=model.max_input_change_percent,
        validated_at=model.validated_at,
        max_age_days=model.max_age_days,
        expires_at=model.expires_at,
        validation_methodology=model.validation_methodology,
        causal_evidence_level=model.causal_evidence_level,
        drift_status=model.drift_status,
        last_drift_check_at=model.last_drift_check_at,
        governance_warnings=governance.warnings,
        provenance="registered_validated_response_model",
        limitations=limitations,
    )


def response_model_to_dict(
    model: ResponseModel,
) -> dict[str, Any]:
    return asdict(model)


def response_estimate_to_dict(
    estimate: ResponseEstimate,
) -> dict[str, Any]:
    return asdict(estimate)


def governance_assessment_to_dict(
    assessment: GovernanceAssessment,
) -> dict[str, Any]:
    return asdict(assessment)

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    provenance: str
    limitations: list[str]


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
    )


def _validate_model_fields(
    *,
    model_type: str,
    confidence_level: str,
    validation_status: str,
    sample_size: int | None,
    version: int,
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


def list_response_models(
    *,
    validation_status: str | None = None,
) -> list[ResponseModel]:
    query = """
        SELECT
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
            updated_at
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
                """
                SELECT
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
                    updated_at
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
) -> ResponseModel:
    _validate_model_fields(
        model_type=model_type,
        confidence_level=confidence_level,
        validation_status=validation_status,
        sample_size=sample_size,
        version=version,
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
                    updated_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, now(), now()
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
    """
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            if scope_type and scope_value:
                cur.execute(
                    """
                    SELECT
                        id, model_name, input_variable, output_variable,
                        scope_type, scope_value, model_type, coefficient,
                        intercept, training_start, training_end, sample_size,
                        validation_metric_name, validation_metric_value,
                        confidence_level, validation_status, version, notes,
                        created_by, updated_by, created_at, updated_at
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
                """
                SELECT
                    id, model_name, input_variable, output_variable,
                    scope_type, scope_value, model_type, coefficient,
                    intercept, training_start, training_end, sample_size,
                    validation_metric_name, validation_metric_value,
                    confidence_level, validation_status, version, notes,
                    created_by, updated_by, created_at, updated_at
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

    if model.model_type == "elasticity":
        estimated = (
            model.coefficient * x
            + model.intercept
        )

    elif model.model_type == "linear_percent":
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
            "data, scope, assumptions, and validation remain applicable."
        ),
        (
            "A historical/statistical response model does not by itself prove "
            "causality unless the underlying validation method supports a causal "
            "interpretation."
        ),
        (
            "Extrapolation beyond the range represented in the original model "
            "training data may be unreliable."
        ),
        (
            "Management should review model provenance and confidence before "
            "using the estimate for consequential decisions."
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

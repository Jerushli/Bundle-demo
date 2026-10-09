from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.ingestion import get_ingest_connection

RULE_HURDLE_RATE = "investment_hurdle_rate_percent"
RULE_MAX_PAYBACK = "investment_max_payback_months"
RULE_BASELINE_PERIOD = "investment_default_baseline_period_months"

SUPPORTED_RULES = {
    RULE_HURDLE_RATE: {"unit": "percent", "minimum": 0.0, "maximum": 500.0},
    RULE_MAX_PAYBACK: {"unit": "months", "minimum": 1.0, "maximum": 240.0},
    RULE_BASELINE_PERIOD: {"unit": "months", "minimum": 1.0, "maximum": 120.0},
}

SUPPORTED_SCOPE_TYPES = {
    "region",
    "country",
    "product",
    "segment",
    "department",
    "channel",
    "category",
}

@dataclass(frozen=True)
class BusinessRule:
    rule_name: str
    numeric_value: float
    unit: str
    description: str
    is_active: bool
    updated_by: str | None
    created_at: Any
    updated_at: Any

@dataclass(frozen=True)
class ScopedBusinessRule:
    scope_type: str
    scope_value: str
    rule_name: str
    numeric_value: float
    unit: str
    description: str
    is_active: bool
    updated_by: str | None
    created_at: Any
    updated_at: Any

def _validate_rule_value(*, rule_name: str, numeric_value: float):
    spec = SUPPORTED_RULES.get(rule_name)
    if not spec:
        raise ValueError(f"Unsupported business rule: {rule_name}")
    value = float(numeric_value)
    if value < spec["minimum"] or value > spec["maximum"]:
        raise ValueError(
            f"{rule_name} must be between {spec['minimum']} and "
            f"{spec['maximum']} {spec['unit']}."
        )

def _validate_scope(*, scope_type: str, scope_value: str):
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        raise ValueError(
            f"Unsupported scope type {scope_type!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_SCOPE_TYPES))}."
        )
    if not scope_value or not scope_value.strip():
        raise ValueError("scope_value cannot be empty.")

def _row_to_rule(row) -> BusinessRule:
    return BusinessRule(
        rule_name=str(row[0]),
        numeric_value=float(row[1]),
        unit=str(row[2]),
        description=str(row[3] or ""),
        is_active=bool(row[4]),
        updated_by=str(row[5]) if row[5] is not None else None,
        created_at=row[6],
        updated_at=row[7],
    )

def _row_to_scoped_rule(row) -> ScopedBusinessRule:
    return ScopedBusinessRule(
        scope_type=str(row[0]),
        scope_value=str(row[1]),
        rule_name=str(row[2]),
        numeric_value=float(row[3]),
        unit=str(row[4]),
        description=str(row[5] or ""),
        is_active=bool(row[6]),
        updated_by=str(row[7]) if row[7] is not None else None,
        created_at=row[8],
        updated_at=row[9],
    )

def list_business_rules() -> list[BusinessRule]:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT rule_name, numeric_value, unit, description, is_active,
                       updated_by, created_at, updated_at
                FROM bundle.business_rules
                ORDER BY rule_name
                """
            )
            rows = cur.fetchall()
    return [_row_to_rule(row) for row in rows]

def get_business_rule(rule_name: str) -> BusinessRule | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT rule_name, numeric_value, unit, description, is_active,
                       updated_by, created_at, updated_at
                FROM bundle.business_rules
                WHERE rule_name = %s
                LIMIT 1
                """,
                (rule_name,),
            )
            row = cur.fetchone()
    return _row_to_rule(row) if row else None

def get_active_numeric_rule(rule_name: str) -> float:
    rule = get_business_rule(rule_name)
    if not rule:
        raise ValueError(f"Required business rule {rule_name!r} does not exist.")
    if not rule.is_active:
        raise ValueError(f"Required business rule {rule_name!r} is disabled.")
    return float(rule.numeric_value)

def update_business_rule(
    *,
    rule_name: str,
    numeric_value: float,
    updated_by: str,
    description: str | None = None,
    is_active: bool = True,
) -> BusinessRule:
    _validate_rule_value(rule_name=rule_name, numeric_value=numeric_value)
    spec = SUPPORTED_RULES[rule_name]
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.business_rules
                (
                    rule_name, numeric_value, unit, description,
                    is_active, updated_by, created_at, updated_at
                )
                VALUES (%s, %s, %s, COALESCE(%s, ''), %s, %s, now(), now())
                ON CONFLICT (rule_name)
                DO UPDATE SET
                    numeric_value = EXCLUDED.numeric_value,
                    unit = EXCLUDED.unit,
                    description = CASE
                        WHEN EXCLUDED.description = ''
                        THEN bundle.business_rules.description
                        ELSE EXCLUDED.description
                    END,
                    is_active = EXCLUDED.is_active,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                """,
                (
                    rule_name,
                    float(numeric_value),
                    spec["unit"],
                    description,
                    bool(is_active),
                    updated_by,
                ),
            )
            connection.commit()
    updated = get_business_rule(rule_name)
    if not updated:
        raise RuntimeError(
            "Business rule update succeeded but rule could not be reloaded."
        )
    return updated

def list_scoped_business_rules(
    *,
    scope_type: str | None = None,
    scope_value: str | None = None,
) -> list[ScopedBusinessRule]:
    query = """
        SELECT scope_type, scope_value, rule_name, numeric_value, unit,
               description, is_active, updated_by, created_at, updated_at
        FROM bundle.scoped_business_rules
    """
    params: list[Any] = []
    conditions: list[str] = []
    if scope_type is not None:
        conditions.append("scope_type = %s")
        params.append(scope_type)
    if scope_value is not None:
        conditions.append("scope_value = %s")
        params.append(scope_value)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY scope_type, scope_value, rule_name"

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [_row_to_scoped_rule(row) for row in rows]

def get_scoped_business_rule(
    *,
    scope_type: str,
    scope_value: str,
    rule_name: str,
) -> ScopedBusinessRule | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT scope_type, scope_value, rule_name, numeric_value, unit,
                       description, is_active, updated_by, created_at, updated_at
                FROM bundle.scoped_business_rules
                WHERE scope_type = %s
                  AND scope_value = %s
                  AND rule_name = %s
                LIMIT 1
                """,
                (scope_type, scope_value, rule_name),
            )
            row = cur.fetchone()
    return _row_to_scoped_rule(row) if row else None

def update_scoped_business_rule(
    *,
    scope_type: str,
    scope_value: str,
    rule_name: str,
    numeric_value: float,
    updated_by: str,
    description: str | None = None,
    is_active: bool = True,
) -> ScopedBusinessRule:
    _validate_scope(scope_type=scope_type, scope_value=scope_value)
    _validate_rule_value(rule_name=rule_name, numeric_value=numeric_value)
    spec = SUPPORTED_RULES[rule_name]
    clean_scope_value = scope_value.strip()

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.scoped_business_rules
                (
                    scope_type, scope_value, rule_name, numeric_value, unit,
                    description, is_active, updated_by, created_at, updated_at
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, COALESCE(%s, ''),
                    %s, %s, now(), now()
                )
                ON CONFLICT (scope_type, scope_value, rule_name)
                DO UPDATE SET
                    numeric_value = EXCLUDED.numeric_value,
                    unit = EXCLUDED.unit,
                    description = CASE
                        WHEN EXCLUDED.description = ''
                        THEN bundle.scoped_business_rules.description
                        ELSE EXCLUDED.description
                    END,
                    is_active = EXCLUDED.is_active,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                """,
                (
                    scope_type,
                    clean_scope_value,
                    rule_name,
                    float(numeric_value),
                    spec["unit"],
                    description,
                    bool(is_active),
                    updated_by,
                ),
            )
            connection.commit()

    updated = get_scoped_business_rule(
        scope_type=scope_type,
        scope_value=clean_scope_value,
        rule_name=rule_name,
    )
    if not updated:
        raise RuntimeError(
            "Scoped rule update succeeded but rule could not be reloaded."
        )
    return updated

def _resolve_rule(
    *,
    rule_name: str,
    scope_type: str | None,
    scope_value: str | None,
) -> dict[str, Any]:
    if scope_type and scope_value:
        scoped = get_scoped_business_rule(
            scope_type=scope_type,
            scope_value=scope_value,
            rule_name=rule_name,
        )
        if scoped and scoped.is_active:
            return {
                "rule_name": rule_name,
                "numeric_value": float(scoped.numeric_value),
                "unit": scoped.unit,
                "source": "scoped",
                "scope_type": scoped.scope_type,
                "scope_value": scoped.scope_value,
            }

    company = get_business_rule(rule_name)
    if not company:
        raise ValueError(
            f"Required company rule {rule_name!r} does not exist."
        )
    if not company.is_active:
        raise ValueError(
            f"Required company rule {rule_name!r} is disabled."
        )
    return {
        "rule_name": rule_name,
        "numeric_value": float(company.numeric_value),
        "unit": company.unit,
        "source": "company_default",
        "scope_type": None,
        "scope_value": None,
    }

def get_investment_policy(
    *,
    target_column: str | None = None,
    target_value: str | None = None,
) -> dict[str, Any]:
    hurdle = _resolve_rule(
        rule_name=RULE_HURDLE_RATE,
        scope_type=target_column,
        scope_value=target_value,
    )
    payback = _resolve_rule(
        rule_name=RULE_MAX_PAYBACK,
        scope_type=target_column,
        scope_value=target_value,
    )
    baseline = _resolve_rule(
        rule_name=RULE_BASELINE_PERIOD,
        scope_type=target_column,
        scope_value=target_value,
    )

    return {
        "hurdle_rate_percent": hurdle["numeric_value"],
        "max_payback_months": payback["numeric_value"],
        "default_baseline_period_months": baseline["numeric_value"],
        "resolved_rules": {
            RULE_HURDLE_RATE: hurdle,
            RULE_MAX_PAYBACK: payback,
            RULE_BASELINE_PERIOD: baseline,
        },
    }

def business_rule_to_dict(rule: BusinessRule) -> dict[str, Any]:
    return asdict(rule)

def scoped_business_rule_to_dict(
    rule: ScopedBusinessRule,
) -> dict[str, Any]:
    return asdict(rule)

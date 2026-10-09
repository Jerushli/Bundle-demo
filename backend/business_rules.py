from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.ingestion import (
    get_ingest_connection,
)


RULE_HURDLE_RATE = "investment_hurdle_rate_percent"
RULE_MAX_PAYBACK = "investment_max_payback_months"
RULE_BASELINE_PERIOD = "investment_default_baseline_period_months"

SUPPORTED_RULES = {
    RULE_HURDLE_RATE: {
        "unit": "percent",
        "minimum": 0.0,
        "maximum": 500.0,
    },
    RULE_MAX_PAYBACK: {
        "unit": "months",
        "minimum": 1.0,
        "maximum": 240.0,
    },
    RULE_BASELINE_PERIOD: {
        "unit": "months",
        "minimum": 1.0,
        "maximum": 120.0,
    },
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


def _validate_rule_value(
    *,
    rule_name: str,
    numeric_value: float,
):
    spec = SUPPORTED_RULES.get(
        rule_name
    )

    if not spec:
        raise ValueError(
            f"Unsupported business rule: {rule_name}"
        )

    value = float(
        numeric_value
    )

    if value < spec["minimum"] or value > spec["maximum"]:
        raise ValueError(
            f"{rule_name} must be between "
            f"{spec['minimum']} and {spec['maximum']} {spec['unit']}."
        )


def _row_to_rule(
    row,
) -> BusinessRule:
    return BusinessRule(
        rule_name=str(
            row[0]
        ),
        numeric_value=float(
            row[1]
        ),
        unit=str(
            row[2]
        ),
        description=str(
            row[3]
            or ""
        ),
        is_active=bool(
            row[4]
        ),
        updated_by=(
            str(
                row[5]
            )
            if row[5] is not None
            else None
        ),
        created_at=row[6],
        updated_at=row[7],
    )


def list_business_rules(
) -> list[BusinessRule]:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rule_name,
                    numeric_value,
                    unit,
                    description,
                    is_active,
                    updated_by,
                    created_at,
                    updated_at
                FROM bundle.business_rules
                ORDER BY rule_name
                """
            )

            rows = cur.fetchall()

    return [
        _row_to_rule(
            row
        )
        for row in rows
    ]


def get_business_rule(
    rule_name: str,
) -> BusinessRule | None:
    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rule_name,
                    numeric_value,
                    unit,
                    description,
                    is_active,
                    updated_by,
                    created_at,
                    updated_at
                FROM bundle.business_rules
                WHERE rule_name = %s
                LIMIT 1
                """,
                (
                    rule_name,
                ),
            )

            row = cur.fetchone()

    return (
        _row_to_rule(
            row
        )
        if row
        else None
    )


def get_active_numeric_rule(
    rule_name: str,
) -> float:
    rule = get_business_rule(
        rule_name
    )

    if not rule:
        raise ValueError(
            f"Required business rule {rule_name!r} does not exist."
        )

    if not rule.is_active:
        raise ValueError(
            f"Required business rule {rule_name!r} is disabled."
        )

    return float(
        rule.numeric_value
    )


def update_business_rule(
    *,
    rule_name: str,
    numeric_value: float,
    updated_by: str,
    description: str | None = None,
    is_active: bool = True,
) -> BusinessRule:
    _validate_rule_value(
        rule_name=rule_name,
        numeric_value=numeric_value,
    )

    spec = SUPPORTED_RULES[
        rule_name
    ]

    with get_ingest_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bundle.business_rules
                (
                    rule_name,
                    numeric_value,
                    unit,
                    description,
                    is_active,
                    updated_by,
                    created_at,
                    updated_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    COALESCE(
                        %s,
                        ''
                    ),
                    %s,
                    %s,
                    now(),
                    now()
                )
                ON CONFLICT (
                    rule_name
                )
                DO UPDATE SET
                    numeric_value =
                        EXCLUDED.numeric_value,
                    unit =
                        EXCLUDED.unit,
                    description =
                        CASE
                            WHEN EXCLUDED.description = ''
                            THEN bundle.business_rules.description
                            ELSE EXCLUDED.description
                        END,
                    is_active =
                        EXCLUDED.is_active,
                    updated_by =
                        EXCLUDED.updated_by,
                    updated_at =
                        now()
                """,
                (
                    rule_name,
                    float(
                        numeric_value
                    ),
                    spec[
                        "unit"
                    ],
                    description,
                    bool(
                        is_active
                    ),
                    updated_by,
                ),
            )

            connection.commit()

    updated = get_business_rule(
        rule_name
    )

    if not updated:
        raise RuntimeError(
            "Business rule update succeeded but rule could not be reloaded."
        )

    return updated


def get_investment_policy(
) -> dict[str, float]:
    return {
        "hurdle_rate_percent": (
            get_active_numeric_rule(
                RULE_HURDLE_RATE
            )
        ),
        "max_payback_months": (
            get_active_numeric_rule(
                RULE_MAX_PAYBACK
            )
        ),
        "default_baseline_period_months": (
            get_active_numeric_rule(
                RULE_BASELINE_PERIOD
            )
        ),
    }


def business_rule_to_dict(
    rule: BusinessRule,
) -> dict[str, Any]:
    return asdict(
        rule
    )

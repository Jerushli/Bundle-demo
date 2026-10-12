from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.daily_intelligence_evidence import (
    build_daily_evidence_package,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)


FORBIDDEN_CAUSAL_PHRASES = (
    "because",
    "caused by",
    "due to",
    "led to",
    "resulted from",
    "driven by",
)

FORBIDDEN_ACTION_PHRASES = (
    "you should",
    "must invest",
    "must cut",
    "must increase",
    "must decrease",
    "buy ",
    "sell ",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _json_safe(item)
            for item in value
        ]

    return value


def _format_number(value: Any) -> str:
    if value is None:
        return "not available"

    number = Decimal(str(value))

    if number == number.to_integral():
        return f"{int(number):,}"

    rendered = f"{number:,.2f}"

    return rendered.rstrip("0").rstrip(".")


def _format_percent(value: Any) -> str:
    if value is None:
        return "not available"

    return f"{_format_number(value)}%"


def _latest_change_map(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes = (
        evidence
        .get(
            "change_detection",
            {},
        )
        .get(
            "changes",
            [],
        )
    )

    return {
        item["kpi_key"]: item
        for item in changes
        if item.get("kpi_key")
    }


def build_deterministic_fact_markdown(
    evidence: dict[str, Any],
) -> str:
    dataset = evidence.get(
        "dataset",
        {},
    )

    snapshot = evidence.get(
        "kpi_snapshot",
        {},
    )

    change_map = _latest_change_map(
        evidence
    )

    lines = [
        "## Daily Intelligence Facts",
        "",
        (
            f"Dataset: **{dataset.get('dataset_name', 'unknown')}**"
        ),
    ]

    snapshot_date = snapshot.get(
        "snapshot_date"
    )

    if snapshot_date:
        lines.append(
            f"Snapshot date: **{snapshot_date}**"
        )

    lines.extend(
        [
            "",
            "### KPI Snapshot",
            "",
        ]
    )

    kpis = snapshot.get(
        "kpis",
        [],
    )

    if not kpis:
        lines.append(
            "- No successful KPI snapshot is available."
        )

    for kpi in kpis:
        key = kpi.get(
            "kpi_key",
            "unknown",
        )

        display_name = kpi.get(
            "display_name",
            key,
        )

        value = _format_number(
            kpi.get(
                "metric_value"
            )
        )

        line = (
            f"- **{display_name}**: {value}"
        )

        change = change_map.get(
            key
        )

        if change:
            direction = change.get(
                "direction",
                "unknown",
            )

            percent_change = _format_percent(
                change.get(
                    "percentage_change"
                )
            )

            severity = change.get(
                "severity",
                "unclassified",
            )

            line += (
                f" | change: {direction} "
                f"({percent_change}) "
                f"| classification: {severity}"
            )

        lines.append(
            line
        )

    change_section = evidence.get(
        "change_detection",
        {},
    )

    lines.extend(
        [
            "",
            "### Change Detection",
            "",
        ]
    )

    if (
        change_section.get("status")
        != "available"
    ):
        lines.append(
            "- Change evidence is not currently available."
        )
    else:
        counts = change_section.get(
            "severity_counts",
            {},
        )

        lines.append(
            "- Critical changes: "
            + str(
                counts.get(
                    "critical",
                    0,
                )
            )
        )

        lines.append(
            "- Warning changes: "
            + str(
                counts.get(
                    "warning",
                    0,
                )
            )
        )

        lines.append(
            "- Normal changes: "
            + str(
                counts.get(
                    "normal",
                    0,
                )
            )
        )

        lines.append(
            "- Unclassified changes: "
            + str(
                counts.get(
                    "unclassified",
                    0,
                )
            )
        )

    governance = evidence.get(
        "response_model_governance",
        {},
    )

    lines.extend(
        [
            "",
            "### Response-Model Governance",
            "",
        ]
    )

    if governance.get(
        "status"
    ) != "available":
        lines.append(
            "- Response-model governance evidence is unavailable."
        )
    else:
        lines.append(
            "- Registered models reviewed: "
            + str(
                governance.get(
                    "model_count",
                    0,
                )
            )
        )

        lines.append(
            "- Governance warnings: "
            + str(
                governance.get(
                    "warning_count",
                    0,
                )
            )
        )

        for warning in governance.get(
            "warnings",
            [],
        ):
            message = warning.get(
                "message",
                "Governance warning.",
            )

            model_id = warning.get(
                "model_id"
            )

            if model_id is None:
                lines.append(
                    f"- {message}"
                )
            else:
                lines.append(
                    f"- Model {model_id}: {message}"
                )

    forecast = evidence.get(
        "forecast_deviation",
        {},
    )

    lines.extend(
        [
            "",
            "### Forecast Comparison",
            "",
        ]
    )

    if forecast.get(
        "status"
    ) == "not_evaluated":
        lines.append(
            "- Daily forecast-vs-actual comparison has not been evaluated yet."
        )
    else:
        lines.append(
            "- Forecast evidence status: "
            + str(
                forecast.get(
                    "status",
                    "unknown",
                )
            )
        )

    rag = evidence.get(
        "rag_context",
        {},
    )

    lines.extend(
        [
            "",
            "### Document Context",
            "",
        ]
    )

    if rag.get(
        "status"
    ) == "deferred_secure_retrieval":
        lines.append(
            "- Secure document context has not been attached to this brief."
        )
    else:
        lines.append(
            "- Document context status: "
            + str(
                rag.get(
                    "status",
                    "unknown",
                )
            )
        )

    return "\n".join(
        lines
    )


def _fallback_executive_summary(
    evidence: dict[str, Any],
) -> str:
    summary = evidence.get(
        "summary",
        {},
    )

    attention_required = bool(
        summary.get(
            "attention_required"
        )
    )

    if attention_required:
        return (
            "The latest intelligence package contains items that deserve "
            "review. The deterministic evidence below shows the measured "
            "movements and governance signals. No cause should be assumed "
            "unless supported by separate authorized evidence."
        )

    return (
        "The latest intelligence package does not currently show an "
        "elevated change signal under the configured rules. The deterministic "
        "facts below remain the source of truth, and no cause is inferred."
    )


def _validate_llm_summary(
    text: str,
) -> tuple[bool, str | None]:
    cleaned = text.strip()

    if not cleaned:
        return False, "empty_summary"

    # Qualitative LLM section may not introduce any numeric claim.
    if re.search(r"\d", cleaned):
        return False, "numeric_content_not_allowed"

    if any(
        symbol in cleaned
        for symbol in (
            "%",
            "₹",
            "$",
            "€",
            "£",
        )
    ):
        return False, "numeric_or_currency_symbol_not_allowed"

    lowered = cleaned.lower()

    if any(
        phrase in lowered
        for phrase in FORBIDDEN_CAUSAL_PHRASES
    ):
        return False, "unsupported_causal_language"

    if any(
        phrase in lowered
        for phrase in FORBIDDEN_ACTION_PHRASES
    ):
        return False, "autonomous_action_language"

    return True, None


def generate_qualitative_summary(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    fallback = _fallback_executive_summary(
        evidence
    )

    if not GROQ_API_KEY:
        return {
            "summary": fallback,
            "llm_used": False,
            "validation_status": "fallback",
            "validation_reason": "GROQ_API_KEY_missing",
        }

    compact_evidence = {
        "summary": evidence.get(
            "summary",
            {},
        ),
        "change_detection": {
            "status": (
                evidence
                .get(
                    "change_detection",
                    {},
                )
                .get(
                    "status"
                )
            ),
            "severity_counts": (
                evidence
                .get(
                    "change_detection",
                    {},
                )
                .get(
                    "severity_counts",
                    {},
                )
            ),
        },
        "response_model_governance": {
            "status": (
                evidence
                .get(
                    "response_model_governance",
                    {},
                )
                .get(
                    "status"
                )
            ),
            "warning_types": [
                item.get(
                    "type"
                )
                for item in (
                    evidence
                    .get(
                        "response_model_governance",
                        {},
                    )
                    .get(
                        "warnings",
                        [],
                    )
                )
            ],
        },
        "forecast_status": (
            evidence
            .get(
                "forecast_deviation",
                {},
            )
            .get(
                "status"
            )
        ),
        "rag_status": (
            evidence
            .get(
                "rag_context",
                {},
            )
            .get(
                "status"
            )
        ),
    }

    system_prompt = """
You are Bundle Daily Intelligence Writer.

Write one short executive summary using ONLY the evidence provided.

STRICT RULES:
- Do not include any numbers or digits.
- Do not include percentages.
- Do not include currency symbols or monetary amounts.
- Do not calculate anything.
- Do not state or imply a cause.
- Do not recommend autonomous business actions.
- Do not invent forecast results.
- Do not invent document evidence.
- You may say an item deserves review or monitoring.
- Use neutral professional language.
- Maximum three sentences.
- Return plain text only.
""".strip()

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=30.0,
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        _json_safe(
                            compact_evidence
                        ),
                        ensure_ascii=False,
                    ),
                },
            ],
        )

        text = (
            response
            .choices[0]
            .message
            .content
            or ""
        ).strip()

    except Exception as exc:
        return {
            "summary": fallback,
            "llm_used": False,
            "validation_status": "fallback",
            "validation_reason": (
                "groq_error:"
                + type(exc).__name__
            ),
        }

    valid, reason = _validate_llm_summary(
        text
    )

    if not valid:
        return {
            "summary": fallback,
            "llm_used": False,
            "validation_status": "fallback",
            "validation_reason": reason,
        }

    return {
        "summary": text,
        "llm_used": True,
        "validation_status": "passed",
        "validation_reason": None,
    }


def generate_daily_brief(
    *,
    role: str,
    persist: bool = True,
) -> dict[str, Any]:
    evidence = build_daily_evidence_package(
        role=role,
        persist=True,
    )

    qualitative = generate_qualitative_summary(
        evidence
    )

    facts_markdown = (
        build_deterministic_fact_markdown(
            evidence
        )
    )

    markdown = (
        "# Bundle Daily Intelligence Brief\n\n"
        "## Executive Summary\n\n"
        f"{qualitative['summary']}\n\n"
        f"{facts_markdown}\n\n"
        "## Interpretation Guardrail\n\n"
        "This brief reports measured or governed evidence only. "
        "It does not establish causation and does not authorize "
        "autonomous business action."
    )

    result = {
        "source": "daily_intelligence_brief",
        "brief_version": "21.4",
        "dataset_name": (
            evidence
            .get(
                "dataset",
                {},
            )
            .get(
                "dataset_name"
            )
        ),
        "role": role,
        "evidence_package_id": evidence.get(
            "package_id"
        ),
        "evidence_date": (
            evidence
            .get(
                "kpi_snapshot",
                {},
            )
            .get(
                "snapshot_date"
            )
        ),
        "executive_summary": qualitative[
            "summary"
        ],
        "llm_used": qualitative[
            "llm_used"
        ],
        "llm_validation_status": qualitative[
            "validation_status"
        ],
        "llm_validation_reason": qualitative[
            "validation_reason"
        ],
        "markdown": markdown,
        "guardrails": evidence.get(
            "guardrails",
            {},
        ),
    }

    brief_id = None

    if persist:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO bundle.intelligence_daily_briefs (
                        dataset_name,
                        evidence_package_id,
                        evidence_date,
                        role_name,
                        brief_version,
                        executive_summary,
                        markdown,
                        llm_used,
                        llm_validation_status,
                        llm_validation_reason,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        NOW()
                    )
                    RETURNING id
                    """,
                    (
                        result["dataset_name"],
                        result[
                            "evidence_package_id"
                        ],
                        result["evidence_date"],
                        role,
                        "21.4",
                        result[
                            "executive_summary"
                        ],
                        result["markdown"],
                        result["llm_used"],
                        result[
                            "llm_validation_status"
                        ],
                        result[
                            "llm_validation_reason"
                        ],
                    ),
                )

                brief_id = cursor.fetchone()[0]

            connection.commit()

    result["brief_id"] = brief_id
    result["persisted"] = persist

    return _json_safe(
        result
    )


def get_daily_briefs(
    *,
    role: str,
    limit: int = 20,
) -> dict[str, Any]:
    if role not in {
        "admin",
        "analyst",
        "viewer",
    }:
        raise ValueError(
            "role must be one of: admin, analyst, viewer."
        )

    safe_limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS brief_id,
                    dataset_name,
                    evidence_package_id,
                    evidence_date,
                    role_name,
                    brief_version,
                    executive_summary,
                    markdown,
                    llm_used,
                    llm_validation_status,
                    llm_validation_reason,
                    created_at
                FROM bundle.intelligence_daily_briefs
                WHERE role_name = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (
                    role,
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "daily_intelligence_brief",
        "role": role,
        "briefs": _json_safe(
            rows
        ),
    }

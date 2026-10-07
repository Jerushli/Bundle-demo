from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dataset_analytics import (
    execute_dataset_analysis,
    get_active_dataset_schema,
    get_category_value_matches,
)
from backend.dataset_profiles import (
    get_latest_business_profile,
)


load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing."
    )

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

client = Groq(
    api_key=GROQ_API_KEY.strip(),
    timeout=30.0,
)


def _format_number(value: Any) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = int(value)

        return f"{value:,}"

    return str(value)


def _human(name: str) -> str:
    return name.replace("_", " ")


def _contains_column_name(
    question_lower: str,
    column: str,
) -> bool:
    readable = _human(column).lower()

    return (
        readable in question_lower
        or column.lower() in question_lower
    )


def _find_measure(
    question_lower: str,
    measures: list[str],
) -> str | None:
    for measure in measures:
        if _contains_column_name(
            question_lower,
            measure,
        ):
            return measure

    aliases = {
        "revenue": [
            "revenue",
            "sales",
            "gross_sales",
        ],
        "cost": [
            "cogs",
            "cost",
        ],
    }

    for word, candidates in aliases.items():
        if word not in question_lower:
            continue

        for candidate in candidates:
            if candidate in measures:
                return candidate

    return None


def _find_category(
    question_lower: str,
    categories: list[str],
) -> str | None:
    for category in categories:
        if _contains_column_name(
            question_lower,
            category,
        ):
            return category

    return None


def _find_date_column(
    question_lower: str,
    dates: list[str],
) -> str | None:
    for date_column in dates:
        if _contains_column_name(
            question_lower,
            date_column,
        ):
            return date_column

    if dates:
        return dates[0]

    return None


def _is_rag_style_question(
    question_lower: str,
    text_columns: list[str],
) -> bool:
    for column in text_columns:
        if _contains_column_name(
            question_lower,
            column,
        ):
            return True

    rag_words = (
        "complain",
        "complaint",
        "feedback",
        "notes",
        "note",
        "comment",
        "comments",
        "description",
        "explain the document",
        "policy",
        "document",
        "why did the customer",
        "what did the customer say",
    )

    return any(
        word in question_lower
        for word in rag_words
    )


def _deterministic_route(
    question: str,
    *,
    role: str,
) -> dict[str, Any] | None:
    schema = get_active_dataset_schema(
        role=role
    )

    q = " ".join(
        question.lower().split()
    )

    # -----------------------------------------------------
    # FREE TEXT / RAG BOUNDARY
    # -----------------------------------------------------
    if _is_rag_style_question(
        q,
        schema.text_columns,
    ):
        return {
            "answer": (
                "That question requires the RAG knowledge path because it "
                "depends on descriptive text or notes rather than structured "
                "analytics. The structured SQL path will not read those "
                "free-text fields."
            ),
            "rows": [],
            "group_by": None,
            "metric": None,
            "source": "rag_required",
            "tool_name": "rag_required",
            "dataset_name": schema.dataset_name,
            "entity": None,
        }

    measure = _find_measure(
        q,
        schema.measures,
    )

    category = _find_category(
        q,
        schema.categories,
    )

    # -----------------------------------------------------
    # COUNT
    # -----------------------------------------------------
    if (
        "how many records" in q
        or "how many rows" in q
        or "record count" in q
        or "row count" in q
        or q in {
            "how many records are there?",
            "how many records are there",
        }
    ):
        result = execute_dataset_analysis(
            role=role,
            operation="aggregate",
            aggregation="count",
            measure=None,
        )

        return _response_from_result(
            question,
            result,
        )

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------
    trend_requested = any(
        phrase in q
        for phrase in (
            "monthly trend",
            "month by month",
            "month-by-month",
            "yearly trend",
            "annual trend",
            "trend over time",
        )
    )

    if trend_requested and measure:
        date_column = _find_date_column(
            q,
            schema.dates,
        )

        if not date_column:
            return {
                "answer": (
                    "This dataset has no validated date column, so a time "
                    "trend cannot be calculated safely."
                ),
                "rows": [],
                "group_by": None,
                "metric": measure,
                "source": "active_dataset",
                "tool_name": "deterministic_router",
                "dataset_name": schema.dataset_name,
                "entity": None,
            }

        date_grain = (
            "year"
            if (
                "yearly" in q
                or "annual" in q
            )
            else "month"
        )

        result = execute_dataset_analysis(
            role=role,
            operation="trend",
            aggregation="sum",
            measure=measure,
            group_by=date_column,
            date_grain=date_grain,
            limit=20,
        )

        return _response_from_result(
            question,
            result,
        )

    # -----------------------------------------------------
    # COMPARE
    # -----------------------------------------------------
    if (
        q.startswith("compare ")
        or " compare " in f" {q} "
        or " versus " in q
        or " vs " in q
    ) and measure:
        value_matches = (
            get_category_value_matches(
                question,
                role=role,
            )
        )

        resolved_category = category
        resolved_values: list[str] = []

        if resolved_category:
            resolved_values = (
                value_matches.get(
                    resolved_category,
                    [],
                )
            )

        if (
            not resolved_category
            or len(resolved_values) < 2
        ):
            candidates = [
                (
                    column,
                    values,
                )
                for column, values
                in value_matches.items()
                if len(values) >= 2
            ]

            if len(candidates) == 1:
                (
                    resolved_category,
                    resolved_values,
                ) = candidates[0]

        if (
            resolved_category
            and len(resolved_values) >= 2
        ):
            result = execute_dataset_analysis(
                role=role,
                operation="compare",
                aggregation="sum",
                measure=measure,
                group_by=resolved_category,
                values=resolved_values,
                limit=min(
                    20,
                    len(resolved_values),
                ),
            )

            return _response_from_result(
                question,
                result,
            )

    # -----------------------------------------------------
    # GROUPED / TOP-N
    # -----------------------------------------------------
    if measure and category:
        grouped_markers = (
            f" by {_human(category).lower()}",
            "which ",
            "show ",
            "list ",
            "highest",
            "lowest",
            "top ",
            "most ",
            "best ",
        )

        if any(
            marker in q
            for marker in grouped_markers
        ):
            limit = 1 if any(
                marker in q
                for marker in (
                    "highest",
                    "lowest",
                    "most ",
                    "best ",
                    "which ",
                )
            ) else 20

            aggregation = "sum"

            if "average" in q or "mean" in q:
                aggregation = "average"
            elif "minimum" in q or "lowest average" in q:
                aggregation = "minimum"
            elif "maximum" in q or "highest average" in q:
                aggregation = "maximum"

            result = execute_dataset_analysis(
                role=role,
                operation="group",
                aggregation=aggregation,
                measure=measure,
                group_by=category,
                limit=limit,
            )

            return _response_from_result(
                question,
                result,
            )

    # -----------------------------------------------------
    # SIMPLE AGGREGATE
    # -----------------------------------------------------
    if measure:
        aggregation = None

        if (
            "average" in q
            or "mean" in q
        ):
            aggregation = "average"

        elif any(
            phrase in q
            for phrase in (
                "minimum",
                "smallest",
                "lowest",
            )
        ):
            aggregation = "minimum"

        elif any(
            phrase in q
            for phrase in (
                "maximum",
                "largest",
                "highest",
            )
        ):
            aggregation = "maximum"

        elif (
            "total" in q
            or "sum" in q
        ):
            aggregation = "sum"

        if aggregation:
            result = execute_dataset_analysis(
                role=role,
                operation="aggregate",
                aggregation=aggregation,
                measure=measure,
            )

            return _response_from_result(
                question,
                result,
            )

    return None


def _build_tool(
    role: str,
):
    schema = get_active_dataset_schema(
        role=role
    )

    properties: dict[str, Any] = {
        "operation": {
            "type": "string",
            "enum": [
                "aggregate",
                "group",
                "compare",
                "trend",
            ],
        },
        "aggregation": {
            "type": "string",
            "enum": [
                "sum",
                "average",
                "minimum",
                "maximum",
                "count",
            ],
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
        },
    }

    if schema.measures:
        properties["measure"] = {
            "type": "string",
            "enum": schema.measures,
        }

    group_columns = [
        *schema.categories,
        *schema.dates,
    ]

    if group_columns:
        properties["group_by"] = {
            "type": "string",
            "enum": group_columns,
        }

    properties["values"] = {
        "type": "array",
        "items": {
            "type": "string",
        },
    }

    filter_columns = [
        *schema.categories,
        *schema.dates,
        *schema.identifiers,
    ]

    if filter_columns:
        properties["filters"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column": {
                        "type": "string",
                        "enum": filter_columns,
                    },
                    "value": {
                        "type": "string",
                    },
                },
                "required": [
                    "column",
                    "value",
                ],
                "additionalProperties": False,
            },
        }

    if schema.dates:
        properties["date_grain"] = {
            "type": "string",
            "enum": [
                "month",
                "year",
            ],
        }

    return {
        "type": "function",
        "function": {
            "name": "analyze_active_dataset",
            "description": (
                "Run one safe structured analysis against the active "
                "validated company dataset. Omit fields that are not needed. "
                "Never write SQL."
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [
                    "operation",
                    "aggregation",
                ],
                "additionalProperties": False,
            },
        },
    }


def _system_prompt(
    role: str,
) -> str:
    schema = get_active_dataset_schema(
        role=role
    )
    profile = get_latest_business_profile(
        schema.dataset_name
    )

    return f"""
You are Bundle Data Assistant.

ACTIVE DATASET
dataset: {schema.dataset_name}

Measures:
{schema.measures}

Categories:
{schema.categories}

Dates:
{schema.dates}

Identifiers:
{schema.identifiers}

Free-text/RAG columns:
{schema.text_columns}

RULES

- Use analyze_active_dataset for structured company-data questions.
- Never write SQL.
- Never invent column names.
- Omit optional tool arguments when they are not needed. Do not send null.
- aggregate: totals, averages, min/max, counts.
- group: "by region/product/..." and rankings.
- compare: explicitly named category values.
- trend: time series, using a validated date column.
- Free-text, customer notes, documents, complaints, policies and similar
  questions belong to RAG, not structured SQL analytics.
- Keep answers concise and evidence-based.
- Do not make definitive investment decisions from a single measure.

Existing deterministic profile:
{profile.get("quick_summary", "")}
""".strip()


def _format_result(
    question: str,
    result: dict[str, Any],
) -> str:
    rows = result.get(
        "rows",
        [],
    )

    if not rows:
        return (
            "No matching records were found in the active dataset."
        )

    operation = result[
        "operation"
    ]

    metric = _human(
        str(
            result.get(
                "metric",
                "value",
            )
        )
    )

    aggregation = _human(
        str(
            result.get(
                "aggregation",
                "sum",
            )
        )
    )

    if operation == "aggregate":
        value = rows[0].get(
            "value"
        )

        if result.get(
            "metric"
        ) == "count":
            return (
                f"The active dataset contains "
                f"{_format_number(value)} matching record(s)."
            )

        return (
            f"The {aggregation} {metric} is "
            f"{_format_number(value)}."
        )

    if operation == "group":
        leader = rows[0]

        if len(rows) == 1:
            return (
                f"{leader['group_name']} has "
                f"{_format_number(leader['value'])} {metric}."
            )

        return (
            f"{leader['group_name']} has the highest {metric} "
            f"among the returned groups at "
            f"{_format_number(leader['value'])}. "
            f"{len(rows)} group(s) were returned."
        )

    if operation == "compare":
        if len(rows) == 1:
            row = rows[0]

            return (
                f"Only {row['group_name']} matched the requested "
                f"comparison, with {_format_number(row['value'])} "
                f"{metric}."
            )

        comparisons = "; ".join(
            f"{row['group_name']}: {_format_number(row['value'])}"
            for row in rows[:5]
        )

        return (
            f"{metric.capitalize()} comparison — {comparisons}."
        )

    if operation == "trend":
        return (
            f"The {metric} trend returned {len(rows)} "
            f"{result.get('date_grain') or 'time'} period(s)."
        )

    return (
        "The requested analysis was completed."
    )


def _response_from_result(
    question: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    rows = result.get(
        "rows",
        [],
    )

    first_entity = (
        rows[0].get(
            "group_name"
        )
        if rows
        else None
    )

    return {
        "answer": _format_result(
            question,
            result,
        ),
        "rows": rows,
        "group_by": result.get(
            "group_by"
        ),
        "metric": result.get(
            "metric"
        ),
        "source": "active_dataset",
        "tool_name": "analyze_active_dataset",
        "dataset_name": result.get(
            "dataset_name"
        ),
        "entity": first_entity,
    }



def _detail_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_detail_evidence(
    question: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    rows = (
        response.get("rows")
        if isinstance(
            response.get("rows"),
            list,
        )
        else []
    )

    evidence: dict[str, Any] = {
        "dataset_name": response.get("dataset_name"),
        "metric": response.get("metric"),
        "group_by": response.get("group_by"),
        "rows": rows[:20],
    }

    numeric_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        value = _detail_float(
            row.get("value")
        )

        if value is None:
            continue

        numeric_rows.append(
            {
                "group_name": row.get("group_name"),
                "value": value,
            }
        )

    if not numeric_rows:
        return evidence

    q = question.lower()
    group_by = str(
        response.get(
            "group_by",
            "",
        )
        or ""
    )

    if (
        group_by == "total"
        or len(numeric_rows) == 1
    ):
        evidence["analysis_type"] = "aggregate"
        evidence["value"] = numeric_rows[0]["value"]
        return evidence

    if group_by in {
        "month",
        "year",
    } or "trend" in q:
        evidence["analysis_type"] = "trend"

        first = numeric_rows[0]
        last = numeric_rows[-1]

        highest = max(
            numeric_rows,
            key=lambda item: item["value"],
        )

        lowest = min(
            numeric_rows,
            key=lambda item: item["value"],
        )

        absolute_change = (
            last["value"]
            - first["value"]
        )

        percent_change = None

        if first["value"] != 0:
            percent_change = (
                absolute_change
                / abs(first["value"])
                * 100
            )

        evidence.update(
            {
                "first_period": first,
                "last_period": last,
                "highest_period": highest,
                "lowest_period": lowest,
                "absolute_change": absolute_change,
                "percent_change": percent_change,
                "direction": (
                    "upward"
                    if absolute_change > 0
                    else (
                        "downward"
                        if absolute_change < 0
                        else "flat"
                    )
                ),
            }
        )

        return evidence

    ranked = sorted(
        numeric_rows,
        key=lambda item: item["value"],
        reverse=True,
    )

    evidence["analysis_type"] = (
        "compare"
        if (
            "compare" in q
            or " versus " in q
            or " vs " in q
        )
        else "group"
    )

    evidence["leader"] = ranked[0]

    if len(ranked) > 1:
        evidence["runner_up"] = ranked[1]

        gap = (
            ranked[0]["value"]
            - ranked[1]["value"]
        )

        evidence["absolute_gap"] = gap

        if ranked[1]["value"] != 0:
            evidence["relative_gap_percent"] = (
                gap
                / abs(ranked[1]["value"])
                * 100
            )

    total = sum(
        row["value"]
        for row in numeric_rows
    )

    if total != 0:
        evidence["leader_share_percent"] = (
            ranked[0]["value"]
            / total
            * 100
        )

    return evidence


def _format_detail_answer(
    response: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    metric = _human(
        str(
            response.get(
                "metric",
                "value",
            )
            or "value"
        )
    )

    analysis_type = evidence.get(
        "analysis_type"
    )

    if analysis_type == "aggregate":
        return (
            f"Detailed view: the returned {metric} value is "
            f"{_format_number(evidence.get('value'))}. "
            f"This is directly calculated from the active validated "
            f"analytics dataset. A single aggregate supports the numeric "
            f"result, but it does not by itself explain why the value is "
            f"high or low."
        )

    if analysis_type == "group":
        leader = evidence.get(
            "leader"
        )

        if not leader:
            return response.get(
                "answer",
                "No additional evidence is available.",
            )

        parts = [
            (
                f"{leader['group_name']} ranks first for {metric} at "
                f"{_format_number(leader['value'])}."
            )
        ]

        runner_up = evidence.get(
            "runner_up"
        )

        if runner_up:
            parts.append(
                f"The runner-up is {runner_up['group_name']} at "
                f"{_format_number(runner_up['value'])}, so the absolute "
                f"gap is {_format_number(evidence.get('absolute_gap'))}."
            )

        relative_gap = evidence.get(
            "relative_gap_percent"
        )

        if isinstance(
            relative_gap,
            (int, float),
        ):
            parts.append(
                f"The leader is about {relative_gap:.2f}% above the "
                f"runner-up."
            )

        share = evidence.get(
            "leader_share_percent"
        )

        if isinstance(
            share,
            (int, float),
        ):
            parts.append(
                f"It represents about {share:.2f}% of the total across "
                f"the returned groups."
            )

        parts.append(
            "This supports the ranking, but not a causal or investment "
            "conclusion by itself."
        )

        return " ".join(parts)

    if analysis_type == "compare":
        rows = evidence.get(
            "rows",
            [],
        )

        comparison_text = "; ".join(
            f"{row.get('group_name')}: "
            f"{_format_number(row.get('value'))}"
            for row in rows[:10]
            if isinstance(row, dict)
        )

        parts = [
            f"Detailed comparison for {metric}: {comparison_text}."
        ]

        gap = evidence.get(
            "absolute_gap"
        )

        if isinstance(
            gap,
            (int, float),
        ):
            parts.append(
                f"The gap between the top two returned values is "
                f"{_format_number(gap)}."
            )

        relative_gap = evidence.get(
            "relative_gap_percent"
        )

        if isinstance(
            relative_gap,
            (int, float),
        ):
            parts.append(
                f"That is approximately {relative_gap:.2f}% relative "
                f"to the second value."
            )

        return " ".join(parts)

    if analysis_type == "trend":
        first = evidence.get(
            "first_period"
        )
        last = evidence.get(
            "last_period"
        )

        if not first or not last:
            return response.get(
                "answer",
                "No additional trend evidence is available.",
            )

        parts = [
            (
                f"The {metric} pattern is {evidence.get('direction')} "
                f"from {first['group_name']} "
                f"({_format_number(first['value'])}) to "
                f"{last['group_name']} "
                f"({_format_number(last['value'])})."
            )
        ]

        percent_change = evidence.get(
            "percent_change"
        )

        if isinstance(
            percent_change,
            (int, float),
        ):
            parts.append(
                f"The end-to-end change is {percent_change:.2f}%."
            )

        highest = evidence.get(
            "highest_period"
        )

        lowest = evidence.get(
            "lowest_period"
        )

        if highest:
            parts.append(
                f"The highest observed period is "
                f"{highest['group_name']} at "
                f"{_format_number(highest['value'])}."
            )

        if lowest:
            parts.append(
                f"The lowest observed period is "
                f"{lowest['group_name']} at "
                f"{_format_number(lowest['value'])}."
            )

        parts.append(
            "This describes the observed pattern only. Explaining its "
            "cause may require more structured variables or RAG evidence "
            "from notes and documents."
        )

        return " ".join(parts)

    return (
        response.get(
            "answer"
        )
        or "No additional structured evidence is available."
    )


def _apply_answer_mode(
    question: str,
    response: dict[str, Any],
    answer_mode: str,
) -> dict[str, Any]:
    output = dict(
        response
    )

    output["answer_mode"] = (
        answer_mode
    )

    if (
        answer_mode != "detailed"
        or output.get(
            "source"
        ) != "active_dataset"
    ):
        return output

    evidence = _build_detail_evidence(
        question,
        output,
    )

    output["evidence"] = (
        evidence
    )

    output["answer"] = (
        _format_detail_answer(
            output,
            evidence,
        )
    )

    return output


def process_dataset_chat(
    question: str,
    history: list[dict] | None = None,
    context: dict | None = None,
    answer_mode: str = "summary",
    role: str = "analyst",
) -> dict[str, Any]:
    if answer_mode not in {
        "summary",
        "detailed",
    }:
        raise ValueError(
            "answer_mode must be summary or detailed."
        )
    # Fast, predictable route for common analytics questions.
    deterministic = _deterministic_route(
        question,
        role=role,
    )

    if deterministic is not None:
        return _apply_answer_mode(
            question,
            deterministic,
            answer_mode,
        )

    messages = [
        {
            "role": "system",
            "content": _system_prompt(
                role
            ),
        }
    ]

    if history:
        for item in history[-6:]:
            message_role = item.get(
                "role"
            )

            content = item.get(
                "content"
            )

            if (
                message_role in {
                    "user",
                    "assistant",
                }
                and content
            ):
                messages.append(
                    {
                        "role": message_role,
                        "content": str(
                            content
                        )[:4000],
                    }
                )

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=[
            _build_tool(
                role
            )
        ],
        tool_choice="auto",
        temperature=0,
    )

    message = response.choices[
        0
    ].message

    tool_calls = getattr(
        message,
        "tool_calls",
        None,
    )

    if not tool_calls:
        answer = (
            message.content
            or (
                "I could not determine a safe structured "
                "analysis for that question."
            )
        )

        return _apply_answer_mode(
            question,
            {
                "answer": answer,
                "rows": [],
                "group_by": None,
                "metric": None,
                "source": "active_dataset",
                "tool_name": "no_tool",
            },
            answer_mode,
        )

    tool_call = tool_calls[0]

    if (
        tool_call.function.name
        != "analyze_active_dataset"
    ):
        raise ValueError(
            "The model requested an unsupported dataset tool."
        )

    try:
        arguments = json.loads(
            tool_call.function.arguments
            or "{}"
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "The model returned invalid tool arguments."
        ) from exc

    # Drop explicit nulls if a provider emits them anyway.
    arguments = {
        key: value
        for key, value
        in arguments.items()
        if value is not None
    }

    result = execute_dataset_analysis(
        role=role,
        operation=arguments.get(
            "operation"
        ),
        aggregation=arguments.get(
            "aggregation",
            "sum",
        ),
        measure=arguments.get(
            "measure"
        ),
        group_by=arguments.get(
            "group_by"
        ),
        values=arguments.get(
            "values"
        ),
        filters=arguments.get(
            "filters"
        ),
        limit=arguments.get(
            "limit",
            10,
        ),
        date_grain=arguments.get(
            "date_grain"
        ),
    )

    return _apply_answer_mode(
        question,
        _response_from_result(
            question,
            result,
        ),
        answer_mode,
    )

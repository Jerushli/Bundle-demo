from __future__ import annotations

import json
import os
from statistics import mean
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
from backend.rag_bridge import (
    retrieve_rag_evidence,
)


load_dotenv(
    override=True
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

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


CAUSAL_PHRASES = (
    "why ",
    "why is",
    "why are",
    "reason",
    "reasons",
    "driver",
    "drivers",
    "driving",
    "cause",
    "causing",
    "performing better",
    "performing worse",
    "performance",
    "underperform",
    "outperform",
    "doing better",
    "doing worse",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def _human(
    value: str,
) -> str:
    return value.replace(
        "_",
        " ",
    )


def _mentioned_measure(
    question: str,
    measures: list[str],
) -> str | None:
    q = _normalize(
        question
    )

    for measure in measures:
        if (
            measure.lower() in q
            or _human(
                measure
            ).lower() in q
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
        if word not in q:
            continue

        for candidate in candidates:
            if candidate in measures:
                return candidate

    return None


def _choose_default_measure(
    *,
    dataset_name: str,
    measures: list[str],
) -> str | None:
    if not measures:
        return None

    try:
        profile = get_latest_business_profile(
            dataset_name
        )

        primary = profile.get(
            "primary_measure"
        )

        if (
            isinstance(
                primary,
                str,
            )
            and primary in measures
        ):
            return primary

    except Exception:
        # Hybrid routing can still work using the validated schema.
        pass

    for preferred in (
        "profit",
        "sales",
        "revenue",
        "gross_sales",
    ):
        if preferred in measures:
            return preferred

    return measures[0]


def _resolve_entity(
    *,
    question: str,
    role: str,
) -> tuple[
    str | None,
    str | None,
]:
    matches = get_category_value_matches(
        question,
        role=role,
    )

    candidates = [
        (
            column,
            values[0],
        )
        for column, values
        in matches.items()
        if len(values) == 1
    ]

    if len(candidates) == 1:
        return candidates[0]

    # If several columns matched, prefer common business dimensions.
    priority = [
        "region",
        "country",
        "product",
        "segment",
        "department",
        "channel",
        "category",
    ]

    for wanted in priority:
        values = matches.get(
            wanted
        )

        if (
            values
            and len(
                values
            ) == 1
        ):
            return (
                wanted,
                values[0],
            )

    return (
        None,
        None,
    )


def should_use_hybrid(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    if not any(
        phrase in q
        for phrase in CAUSAL_PHRASES
    ):
        return False

    schema = get_active_dataset_schema(
        role=role
    )

    # Pure document/customer-note questions should remain RAG-only.
    pure_rag_markers = (
        "customer complain",
        "customer complaint",
        "customer notes",
        "what did the customer say",
        "what do the notes say",
        "document say",
        "policy say",
    )

    if any(
        marker in q
        for marker in pure_rag_markers
    ):
        return False

    explicit_measure = _mentioned_measure(
        question,
        schema.measures,
    )

    category, entity = _resolve_entity(
        question=question,
        role=role,
    )

    return bool(
        explicit_measure
        or (
            category
            and entity
        )
    )


def _numeric_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []

    for row in rows:
        try:
            value = float(
                row.get(
                    "value"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        output.append(
            {
                "group_name": str(
                    row.get(
                        "group_name",
                        ""
                    )
                ),
                "value": value,
            }
        )

    return output


def _structured_evidence(
    *,
    question: str,
    role: str,
    dataset_name: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    schema = get_active_dataset_schema(
        role=role
    )

    measure = (
        _mentioned_measure(
            question,
            schema.measures,
        )
        or _choose_default_measure(
            dataset_name=dataset_name,
            measures=schema.measures,
        )
    )

    if not measure:
        raise ValueError(
            "No permitted numeric measure is available for hybrid analysis."
        )

    category, entity = _resolve_entity(
        question=question,
        role=role,
    )

    if not category or not entity:
        raise ValueError(
            "Hybrid analysis requires one clearly identified business "
            "entity such as a region, country, product, or segment."
        )

    result = execute_dataset_analysis(
        role=role,
        operation="group",
        aggregation="sum",
        measure=measure,
        group_by=category,
        limit=20,
    )

    rows = _numeric_rows(
        result.get(
            "rows",
            [],
        )
    )

    if not rows:
        raise ValueError(
            "The structured analysis returned no numeric evidence."
        )

    target = next(
        (
            row
            for row in rows
            if row[
                "group_name"
            ].lower()
            == entity.lower()
        ),
        None,
    )

    if target is None:
        raise ValueError(
            f"{entity!r} was not present in the permitted grouped result."
        )

    ranked = sorted(
        rows,
        key=lambda row: row[
            "value"
        ],
        reverse=True,
    )

    rank = next(
        index
        for index, row
        in enumerate(
            ranked,
            start=1,
        )
        if row[
            "group_name"
        ].lower()
        == entity.lower()
    )

    peer_values = [
        row["value"]
        for row in rows
        if row[
            "group_name"
        ].lower()
        != entity.lower()
    ]

    peer_average = (
        mean(
            peer_values
        )
        if peer_values
        else None
    )

    total = sum(
        row["value"]
        for row in rows
    )

    gap_vs_peer_average = (
        target["value"]
        - peer_average
        if peer_average is not None
        else None
    )

    gap_percent = None

    if (
        peer_average is not None
        and peer_average != 0
    ):
        gap_percent = (
            gap_vs_peer_average
            / abs(
                peer_average
            )
            * 100
        )

    evidence = {
        "dataset_name": dataset_name,
        "measure": measure,
        "group_by": category,
        "entity": entity,
        "entity_value": target[
            "value"
        ],
        "rank": rank,
        "group_count": len(
            ranked
        ),
        "peer_average": peer_average,
        "gap_vs_peer_average": (
            gap_vs_peer_average
        ),
        "gap_vs_peer_average_percent": (
            gap_percent
        ),
        "share_percent": (
            target["value"]
            / total
            * 100
            if total != 0
            else None
        ),
        "leader": ranked[0],
        "rows": ranked,
    }

    return (
        result,
        evidence,
    )


def _document_prompt(
    evidence: list[
        dict[str, Any]
    ],
) -> str:
    blocks = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):
        text = str(
            item.get(
                "text",
                "",
            )
        ).strip()

        if len(
            text
        ) > 2500:
            text = (
                text[:2500]
                + "..."
            )

        blocks.append(
            "\n".join(
                [
                    f"[{index}]",
                    (
                        "document_id: "
                        f"{item.get('document_id')}"
                    ),
                    (
                        "title: "
                        f"{item.get('title')}"
                    ),
                    (
                        "document_type: "
                        f"{item.get('document_type')}"
                    ),
                    (
                        "similarity: "
                        f"{item.get('similarity')}"
                    ),
                    "text:",
                    text,
                ]
            )
        )

    return "\n\n".join(
        blocks
    )


def _citation_list(
    evidence: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:
    return [
        {
            "index": index,
            "document_id": item.get(
                "document_id"
            ),
            "title": item.get(
                "title"
            ),
            "document_type": item.get(
                "document_type"
            ),
            "access_level": item.get(
                "access_level"
            ),
            "similarity": item.get(
                "similarity"
            ),
        }
        for index, item in enumerate(
            evidence,
            start=1,
        )
    ]


def process_hybrid_chat(
    *,
    question: str,
    role: str,
    dataset_name: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    structured_result, structured = (
        _structured_evidence(
            question=question,
            role=role,
            dataset_name=dataset_name,
        )
    )

    entity = str(
        structured[
            "entity"
        ]
    )

    measure = str(
        structured[
            "measure"
        ]
    )

    rag_query = (
        f"{question}\n"
        f"Entity: {entity}\n"
        f"Business measure: {_human(measure)}\n"
        "Look for evidence that may explain operational, customer, "
        "support, risk, delivery, incident, product, or service factors."
    )

    documents = retrieve_rag_evidence(
        question=rag_query,
        role=role,
        dataset_name=dataset_name,
        limit=5,
    )

    style = (
        "Give a concise answer in 3 to 5 sentences."
        if answer_mode
        == "summary"
        else (
            "Give a detailed but focused analysis. "
            "Clearly separate measured facts, document evidence, "
            "and uncertainty."
        )
    )

    system_prompt = """
You are Bundle Data Assistant performing HYBRID analysis.

You receive:
1. structured SQL evidence calculated by the authorized analytics engine, and
2. an already-authorized document evidence set retrieved by secure RAG.

RULES

1. Treat structured evidence as the source for numeric/ranking claims.
2. Treat document evidence as possible explanatory/context evidence only.
3. Cite document-derived claims with [1], [2], etc.
4. Do not attach document citation numbers to SQL-only numeric claims.
5. Correlation or co-occurrence is not proof of causation.
6. If documents do not actually explain the structured result, explicitly say
   the measurable difference is established but the cause is not established.
7. Never invent a causal driver.
8. Never infer hidden or restricted documents.
9. Do not expose access-control implementation details.
10. Keep the distinction between "what happened" and "why it happened" clear.
""".strip()

    user_prompt = f"""
QUESTION

{question}

RESPONSE STYLE

{style}

STRUCTURED SQL EVIDENCE

{json.dumps(structured, ensure_ascii=False, indent=2)}

AUTHORIZED DOCUMENT EVIDENCE

{_document_prompt(documents) if documents else "No authorized relevant document evidence was retrieved."}
""".strip()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0,
    )

    answer = (
        response.choices[0]
        .message.content
        or (
            "The hybrid evidence was collected, but an answer "
            "could not be generated."
        )
    ).strip()

    return {
        "answer": answer,
        "rows": structured_result.get(
            "rows",
            [],
        ),
        "group_by": structured_result.get(
            "group_by"
        ),
        "metric": structured_result.get(
            "metric"
        ),
        "source": "hybrid",
        "tool_name": "hybrid_sql_rag",
        "dataset_name": dataset_name,
        "entity": structured.get(
            "entity"
        ),
        "answer_mode": answer_mode,
        "citations": _citation_list(
            documents
        ),
        "hybrid_evidence": {
            "structured": structured,
            "document_count": len(
                documents
            ),
        },
    }

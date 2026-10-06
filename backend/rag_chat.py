from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

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


def _citation_list(
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    citations = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):
        citations.append(
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
        )

    return citations


def _evidence_prompt(
    evidence: list[dict[str, Any]],
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

        # Keep each evidence item bounded before sending to Groq.
        if len(text) > 3000:
            text = (
                text[:3000]
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
                        "access_level: "
                        f"{item.get('access_level')}"
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


def process_rag_chat(
    *,
    question: str,
    role: str,
    dataset_name: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    evidence = retrieve_rag_evidence(
        question=question,
        role=role,
        dataset_name=dataset_name,
        limit=5,
    )

    if not evidence:
        return {
            "answer": (
                "I could not find authorized document evidence "
                "relevant enough to answer that question."
            ),
            "rows": [],
            "group_by": None,
            "metric": None,
            "source": "rag",
            "tool_name": "secure_rag",
            "dataset_name": dataset_name,
            "answer_mode": answer_mode,
            "citations": [],
        }

    detail_instruction = (
        "Give a concise answer in 2 to 4 sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed but focused explanation. "
            "Separate observed evidence from inference."
        )
    )

    system_prompt = """
You are Bundle Data Assistant.

You are answering from an already-authorized RAG evidence set.

SECURITY AND EVIDENCE RULES

1. Use only the evidence supplied in this prompt.
2. Do not invent facts that are not supported by the evidence.
3. Do not claim that you searched documents outside the supplied evidence.
4. Cite factual claims using [1], [2], etc.
5. A citation number refers to the correspondingly numbered evidence item.
6. If the evidence is insufficient, say so.
7. Do not reveal or infer hidden/restricted documents.
8. Do not expose access-control implementation details to the end user.
9. Do not treat similarity score as proof that a claim is true.
""".strip()

    user_prompt = f"""
QUESTION

{question}

RESPONSE STYLE

{detail_instruction}

AUTHORIZED EVIDENCE

{_evidence_prompt(evidence)}
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
        response.choices[0].message.content
        or (
            "The authorized evidence was retrieved, but "
            "an answer could not be generated."
        )
    ).strip()

    return {
        "answer": answer,
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "rag",
        "tool_name": "secure_rag",
        "dataset_name": dataset_name,
        "answer_mode": answer_mode,
        "citations": _citation_list(
            evidence
        ),
    }

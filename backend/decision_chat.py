from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.decision_evidence import build_decision_evidence, is_decision_question

load_dotenv(override=True)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing.")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
client = Groq(api_key=GROQ_API_KEY.strip(), timeout=30.0)

RECOMMENDATION_CLASSES = {
    "consider",
    "cautious_consider",
    "hold",
    "investigate_further",
    "insufficient_evidence",
}


def should_use_decision(*, question: str, role: str) -> bool:
    return is_decision_question(question)


def _measure_signals(package: dict[str, Any]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    structured = package.get("structured_evidence") or {}
    measures = structured.get("measures") or {}
    target_value = structured.get("target_value") or "Target"

    for measure, evidence in measures.items():
        if not evidence.get("available"):
            continue
        rank = evidence.get("rank")
        group_count = evidence.get("group_count")
        gap_pct = evidence.get("gap_vs_peer_average_percent")

        if isinstance(rank, int) and isinstance(group_count, int) and group_count > 1:
            if rank == 1:
                positive.append(f"{target_value} ranks 1/{group_count} on {measure}.")
            elif rank <= max(1, group_count // 3):
                positive.append(f"{target_value} ranks {rank}/{group_count} on {measure}.")
            elif rank > (group_count + 1) / 2:
                negative.append(f"{target_value} ranks {rank}/{group_count} on {measure}.")

        if isinstance(gap_pct, (int, float)):
            if gap_pct >= 10:
                positive.append(f"{measure} is {gap_pct:.1f}% above the peer average.")
            elif gap_pct <= -10:
                negative.append(f"{measure} is {abs(gap_pct):.1f}% below the peer average.")

    return positive, negative


def _deterministic_assessment(package: dict[str, Any]) -> dict[str, Any]:
    if not package.get("target_resolved"):
        return {
            "recommendation": "insufficient_evidence",
            "confidence": "low",
            "positive_signals": [],
            "negative_signals": [],
            "decision_basis": "The decision target is not resolved.",
        }

    quality = package.get("evidence_quality") or {}
    if not quality.get("structured_available"):
        return {
            "recommendation": "insufficient_evidence",
            "confidence": "low",
            "positive_signals": [],
            "negative_signals": [],
            "decision_basis": "No permitted structured performance evidence is available.",
        }

    positive, negative = _measure_signals(package)
    roi_supported = bool(quality.get("quantified_roi_model_available"))
    rag_count = int(quality.get("rag_document_count") or 0)
    forecast_available = bool(quality.get("forecast_available"))
    forecast_confidence = quality.get("forecast_confidence")

    if len(negative) >= 2 and len(negative) > len(positive):
        recommendation = "hold"
    elif len(positive) >= 2 and len(positive) > len(negative):
        recommendation = "consider" if roi_supported else "cautious_consider"
    else:
        recommendation = "investigate_further"

    confidence_score = 0
    if quality.get("structured_available"):
        confidence_score += 2
    if forecast_available:
        confidence_score += 1
    if forecast_confidence in {"medium", "high"}:
        confidence_score += 1
    if rag_count > 0:
        confidence_score += 1
    if roi_supported:
        confidence_score += 2

    if confidence_score >= 6:
        confidence = "high"
    elif confidence_score >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if not roi_supported and confidence == "high":
        confidence = "medium"

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "positive_signals": positive,
        "negative_signals": negative,
        "decision_basis": (
            "Recommendation class is determined from permitted structured performance signals "
            "and evidence availability. Quantified ROI is not inferred without a validated "
            "investment-response model."
        ),
    }


def _document_citations(package: dict[str, Any]) -> list[dict[str, Any]]:
    results = ((package.get("rag_evidence") or {}).get("results") or [])
    return [
        {
            "index": index,
            "document_id": item.get("document_id"),
            "title": item.get("title"),
            "document_type": item.get("document_type"),
            "access_level": item.get("access_level"),
            "similarity": item.get("similarity"),
        }
        for index, item in enumerate(results, start=1)
    ]


def _document_prompt(package: dict[str, Any]) -> str:
    results = ((package.get("rag_evidence") or {}).get("results") or [])
    if not results:
        return "No authorized decision-relevant documents were retrieved."

    blocks = []
    for index, item in enumerate(results, start=1):
        text = str(item.get("text", "")).strip()
        if len(text) > 2200:
            text = text[:2200] + "..."
        blocks.append(
            "\n".join(
                [
                    f"[{index}]",
                    f"document_id: {item.get('document_id')}",
                    f"title: {item.get('title')}",
                    f"document_type: {item.get('document_type')}",
                    f"similarity: {item.get('similarity')}",
                    "text:",
                    text,
                ]
            )
        )
    return "\n\n".join(blocks)


def _fallback_answer(*, package: dict[str, Any], assessment: dict[str, Any]) -> str:
    recommendation = assessment["recommendation"].replace("_", " ").title()
    confidence = assessment["confidence"].title()
    positive = assessment["positive_signals"]
    negative = assessment["negative_signals"]
    target_name = (package.get("target") or {}).get("value") or "the target"

    parts = [
        f"**Recommendation:** {recommendation} for {target_name}.",
        f"**Confidence:** {confidence}.",
    ]
    if positive:
        parts.append("**Supporting evidence:** " + " ".join(positive[:3]))
    if negative:
        parts.append("**Counter-evidence:** " + " ".join(negative[:3]))
    parts.append(
        "**Important limitation:** Bundle does not yet have a validated investment-to-profit "
        "response model, so it cannot provide a defensible quantified ROI."
    )
    return "\n\n".join(parts)


def _explain_decision(*, question: str, package: dict[str, Any], assessment: dict[str, Any], answer_mode: str) -> str:
    style = (
        "Give a concise executive decision assessment in 5 to 8 sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed executive decision assessment. Use clear sections for Recommendation, "
            "Current Performance, Forecast Context, Document Evidence, Risks, Missing Information, "
            "and Confidence."
        )
    )

    system_prompt = """
You are Bundle Data Assistant producing an evidence-grounded management decision assessment.

A deterministic layer has already selected the recommendation class. YOU MUST NOT change it.

Rules:
1. State the exact supplied recommendation class in human-readable form.
2. Never fabricate ROI, payback period, NPV, IRR, or causal uplift.
3. Never say an investment WILL increase sales/profit unless a validated causal model is supplied.
4. Structured metrics are observed facts.
5. Forecast evidence may be overall-dataset rather than target-specific. Respect the scope note.
6. Document evidence can provide context but does not prove causation.
7. Cite document-derived claims with [1], [2], etc.
8. Do not attach document citations to SQL-only facts.
9. Explicitly mention material risks and missing information.
10. Confidence is an evidence-quality label, not a probability.
11. cautious_consider means due diligence or a bounded pilot, not full-scale investment.
12. hold must be justified with observed negative signals.
13. insufficient_evidence must state what information is required before deciding.
""".strip()

    package_for_model = dict(package)
    rag = dict(package_for_model.get("rag_evidence") or {})
    rag["results"] = [
        {
            "citation_index": index,
            "document_id": item.get("document_id"),
            "title": item.get("title"),
            "document_type": item.get("document_type"),
            "similarity": item.get("similarity"),
        }
        for index, item in enumerate(((package.get("rag_evidence") or {}).get("results") or []), start=1)
    ]
    package_for_model["rag_evidence"] = rag

    user_prompt = f"""
QUESTION
{question}

RESPONSE STYLE
{style}

FIXED DETERMINISTIC ASSESSMENT
{json.dumps(assessment, ensure_ascii=False, indent=2)}

DECISION EVIDENCE PACKAGE
{json.dumps(package_for_model, ensure_ascii=False, indent=2, default=str)}

AUTHORIZED DOCUMENT TEXT
{_document_prompt(package)}
""".strip()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )
        answer = (response.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception:
        pass

    return _fallback_answer(package=package, assessment=assessment)


def _decision_rows(package: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    structured = package.get("structured_evidence") or {}
    measures = structured.get("measures") or {}
    chosen_measure = None
    chosen = None

    for measure in ["profit", "sales", "revenue"]:
        evidence = measures.get(measure)
        if evidence and evidence.get("available"):
            chosen_measure = measure
            chosen = evidence
            break

    if chosen is None:
        for measure, evidence in measures.items():
            if evidence.get("available"):
                chosen_measure = measure
                chosen = evidence
                break

    if chosen is None:
        return [], None

    rows = [
        {
            "group_name": structured.get("target_value") or "Target",
            "value": chosen["target_value"],
        }
    ]
    if chosen.get("peer_average") is not None:
        rows.append({"group_name": "Peer average", "value": chosen["peer_average"]})
    return rows, chosen_measure


def process_decision_chat(*, question: str, role: str, answer_mode: str = "summary") -> dict[str, Any]:
    package = build_decision_evidence(question=question, role=role)
    assessment = _deterministic_assessment(package)

    if assessment["recommendation"] not in RECOMMENDATION_CLASSES:
        raise RuntimeError("Decision assessment produced an invalid recommendation class.")

    answer = _explain_decision(
        question=question,
        package=package,
        assessment=assessment,
        answer_mode=answer_mode,
    )
    rows, metric = _decision_rows(package)

    return {
        "answer": answer,
        "rows": rows,
        "group_by": "decision_evidence" if rows else None,
        "metric": metric,
        "source": "decision",
        "tool_name": "decision_assessment",
        "answer_mode": answer_mode,
        "citations": _document_citations(package),
        "decision": {"assessment": assessment, "evidence": package},
        "evidence": package,
    }

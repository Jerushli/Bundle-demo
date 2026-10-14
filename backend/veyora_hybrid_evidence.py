from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from backend.massive_data_intelligence import (
    get_group_ranking,
    get_sla_miss_rate,
)


DEFAULT_MINIMUM_SIMILARITY = 0.20
KNOWN_REGIONS = (
    "North",
    "South",
    "East",
    "West",
)


def detect_region(
    question: str,
) -> str | None:
    for region in KNOWN_REGIONS:
        if re.search(
            rf"\b{re.escape(region)}\b",
            question,
            flags=re.IGNORECASE,
        ):
            return region

    return None


def _project_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )


def _rag_python() -> Path:
    return (
        _project_root()
        / ".venv_rag"
        / "Scripts"
        / "python.exe"
    )


def retrieve_rag(
    question: str,
    *,
    dataset_name: str,
    role: str,
    limit: int = 5,
) -> dict[str, Any]:
    rag_python = _rag_python()

    if not rag_python.exists():
        raise RuntimeError(
            f"RAG Python not found: {rag_python}"
        )

    process = subprocess.run(
        [
            str(rag_python),
            "-m",
            "backend.veyora_rag_search",
            question,
            "--dataset-name",
            dataset_name,
            "--role",
            role,
            "--limit",
            str(limit),
            "--minimum-similarity",
            str(
                DEFAULT_MINIMUM_SIMILARITY
            ),
        ],
        cwd=_project_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        raise RuntimeError(
            "RAG retrieval failed:\n"
            + (
                process.stderr
                or process.stdout
            ).strip()
        )

    if not process.stdout.strip():
        raise RuntimeError(
            "RAG retrieval returned no JSON output."
        )

    return json.loads(
        process.stdout
    )


def build_hybrid_evidence(
    question: str,
    *,
    dataset_name: str = "veyora_massive",
    role: str = "analyst",
) -> dict[str, Any]:
    lowered = (
        question
        .strip()
        .lower()
    )

    if "sla" in lowered:
        structured = (
            get_sla_miss_rate(
                dataset_name
            )
        )

    elif "downtime" in lowered:
        structured = (
            get_group_ranking(
                dataset_name,
                metric="downtime_hours",
                group_by="region",
                aggregation="avg",
                limit=10,
            )
        )

    else:
        structured = {
            "operation": (
                "no_structured_operation_selected"
            ),
            "dataset_name": (
                dataset_name
            ),
            "rows": [],
        }

    rag = retrieve_rag(
        question,
        dataset_name=dataset_name,
        role=role,
        limit=5,
    )

    detected_region = (
        detect_region(
            question
        )
    )

    return {
        "source": (
            "veyora_hybrid_evidence"
        ),
        "dataset_name": (
            dataset_name
        ),
        "role": role,
        "question": question,

        "structured_evidence": (
            structured
        ),

        "rag_evidence": (
            rag.get(
                "results",
                [],
            )
        ),

        "rag_retrieval": {
            "detected_region": (
                rag.get(
                    "detected_region"
                )
            ),
            "minimum_similarity": (
                rag.get(
                    "minimum_similarity"
                )
            ),
            "result_count": (
                rag.get(
                    "result_count",
                    0,
                )
            ),
            "region_filter_applied": (
                rag.get(
                    "region_filter_applied",
                    False,
                )
            ),
            "duplicate_suppression_applied": (
                rag.get(
                    "duplicate_suppression_applied",
                    False,
                )
            ),
        },

        "guardrails": {
            "numeric_truth_source": (
                "PostgreSQL"
            ),
            "rag_role_filtered": True,
            "rag_region_filtered_when_present": (
                detected_region is None
                or bool(
                    rag.get(
                        "region_filter_applied"
                    )
                )
            ),
            "rag_minimum_similarity_enforced": (
                rag.get(
                    "minimum_similarity"
                )
                is not None
            ),
            "rag_duplicate_suppression_enforced": (
                bool(
                    rag.get(
                        "duplicate_suppression_applied",
                        False,
                    )
                )
            ),
            "llm_used": False,
            "causality_claimed": False,
            "autonomous_action_taken": False,
        },

        "interpretation_rule": (
            "SQL establishes what happened numerically. "
            "RAG supplies related operational observations. "
            "When a region is named, only region-scoped "
            "evidence is eligible. Retrieved notes are "
            "associations, not proven causes."
        ),
    }


def main() -> None:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "question"
    )

    parser.add_argument(
        "--dataset-name",
        default="veyora_massive",
    )

    parser.add_argument(
        "--role",
        default="analyst",
        choices=[
            "admin",
            "analyst",
            "viewer",
        ],
    )

    args = parser.parse_args()

    result = (
        build_hybrid_evidence(
            args.question,
            dataset_name=(
                args.dataset_name
            ),
            role=args.role,
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()

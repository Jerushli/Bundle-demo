from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


SENTINEL = "BUNDLE_RAG_JSON="

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

DEFAULT_RAG_PYTHON = (
    PROJECT_ROOT
    / ".venv_rag"
    / "Scripts"
    / "python.exe"
)


def _rag_python() -> Path:
    configured = os.getenv(
        "RAG_PYTHON"
    )

    path = (
        Path(configured)
        if configured
        else DEFAULT_RAG_PYTHON
    )

    if not path.exists():
        raise RuntimeError(
            "RAG Python was not found. Set RAG_PYTHON or ensure "
            ".venv_rag\\Scripts\\python.exe exists."
        )

    return path


def retrieve_rag_evidence(
    *,
    question: str,
    role: str,
    dataset_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    command = [
        str(
            _rag_python()
        ),
        "-m",
        "backend.rag_worker",
        "--question",
        question,
        "--role",
        role,
        "--dataset",
        dataset_name,
        "--limit",
        str(
            max(
                1,
                min(
                    int(limit),
                    8,
                ),
            )
        ),
    ]

    completed = subprocess.run(
        command,
        cwd=str(
            PROJECT_ROOT
        ),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=os.environ.copy(),
    )

    payload_line = None

    for line in reversed(
        completed.stdout.splitlines()
    ):
        if line.startswith(
            SENTINEL
        ):
            payload_line = line[
                len(
                    SENTINEL
                ):
            ]

            break

    if payload_line is None:
        error_text = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or "RAG worker returned no JSON payload."
        )

        raise RuntimeError(
            error_text[:1000]
        )

    try:
        payload = json.loads(
            payload_line
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "RAG worker returned invalid JSON."
        ) from exc

    if not payload.get(
        "ok"
    ):
        raise RuntimeError(
            str(
                payload.get(
                    "error"
                )
                or "RAG retrieval failed."
            )
        )

    results = payload.get(
        "results"
    )

    if not isinstance(
        results,
        list,
    ):
        raise RuntimeError(
            "RAG worker returned an invalid result list."
        )

    return results

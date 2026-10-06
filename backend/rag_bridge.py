from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)


SENTINEL = (
    "BUNDLE_RAG_JSON="
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DEFAULT_RAG_PYTHON = (
    PROJECT_ROOT
    / ".venv_rag"
    / "Scripts"
    / "python.exe"
)

RAG_BRIDGE_MODE = os.getenv(
    "RAG_BRIDGE_MODE",
    "service",
).strip().lower()

RAG_WORKER_URL = os.getenv(
    "RAG_WORKER_URL",
    "http://127.0.0.1:8765",
).rstrip(
    "/"
)

RAG_WORKER_TOKEN = os.getenv(
    "RAG_WORKER_TOKEN",
    "",
).strip()


def _rag_python() -> Path:
    configured = os.getenv(
        "RAG_PYTHON"
    )

    path = (
        Path(
            configured
        )
        if configured
        else DEFAULT_RAG_PYTHON
    )

    if not path.exists():
        raise RuntimeError(
            "RAG Python was not found. "
            "Set RAG_PYTHON or ensure "
            ".venv_rag\\Scripts\\python.exe exists."
        )

    return path


def _retrieve_from_service(
    *,
    question: str,
    role: str,
    dataset_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    payload = json.dumps(
        {
            "question": question,
            "role": role,
            "dataset_name": (
                dataset_name
            ),
            "limit": limit,
        }
    ).encode(
        "utf-8"
    )

    headers = {
        "Content-Type": (
            "application/json"
        ),
    }

    if RAG_WORKER_TOKEN:
        headers[
            "X-Bundle-RAG-Token"
        ] = RAG_WORKER_TOKEN

    request = Request(
        f"{RAG_WORKER_URL}/retrieve",
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=90,
        ) as response:
            raw = response.read()

    except HTTPError as exc:
        try:
            details = json.loads(
                exc.read().decode(
                    "utf-8"
                )
            )

            message = details.get(
                "error"
            )

        except Exception:
            message = None

        raise RuntimeError(
            message
            or (
                "RAG worker returned "
                f"HTTP {exc.code}."
            )
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            "Persistent RAG worker is unavailable. "
            "Start it with "
            ".\\.venv_rag\\Scripts\\python.exe "
            "-m backend.rag_service"
        ) from exc

    payload_obj = json.loads(
        raw.decode(
            "utf-8"
        )
    )

    if not payload_obj.get(
        "ok"
    ):
        raise RuntimeError(
            str(
                payload_obj.get(
                    "error"
                )
                or "RAG worker failed."
            )
        )

    results = payload_obj.get(
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


def _retrieve_from_subprocess(
    *,
    question: str,
    role: str,
    dataset_name: str,
    limit: int,
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
            limit
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
            or (
                "RAG worker returned "
                "no JSON payload."
            )
        )

        raise RuntimeError(
            error_text[:1000]
        )

    payload_obj = json.loads(
        payload_line
    )

    if not payload_obj.get(
        "ok"
    ):
        raise RuntimeError(
            str(
                payload_obj.get(
                    "error"
                )
                or "RAG retrieval failed."
            )
        )

    results = payload_obj.get(
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


def retrieve_rag_evidence(
    *,
    question: str,
    role: str,
    dataset_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            8,
        ),
    )

    if (
        RAG_BRIDGE_MODE
        == "subprocess"
    ):
        return _retrieve_from_subprocess(
            question=question,
            role=role,
            dataset_name=dataset_name,
            limit=safe_limit,
        )

    if (
        RAG_BRIDGE_MODE
        != "service"
    ):
        raise RuntimeError(
            "RAG_BRIDGE_MODE must be "
            "'service' or 'subprocess'."
        )

    return _retrieve_from_service(
        question=question,
        role=role,
        dataset_name=dataset_name,
        limit=safe_limit,
    )


def rag_worker_health() -> bool:
    request = Request(
        f"{RAG_WORKER_URL}/health",
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=3,
        ) as response:
            payload = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return bool(
            payload.get(
                "ok"
            )
        )

    except Exception:
        return False

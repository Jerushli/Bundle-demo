from __future__ import annotations

import hmac
import json
import os
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any

from backend.rag_retrieval import (
    rag_results_to_evidence,
    retrieve_allowed_chunks,
)


HOST = os.getenv(
    "RAG_WORKER_HOST",
    "127.0.0.1",
)

PORT = int(
    os.getenv(
        "RAG_WORKER_PORT",
        "8765",
    )
)

WORKER_TOKEN = os.getenv(
    "RAG_WORKER_TOKEN",
    "",
).strip()

MAX_BODY_BYTES = 64 * 1024


def _authorized(
    headers,
) -> bool:
    if not WORKER_TOKEN:
        return True

    supplied = (
        headers.get(
            "X-Bundle-RAG-Token",
            "",
        )
        or ""
    )

    return hmac.compare_digest(
        supplied,
        WORKER_TOKEN,
    )


class Handler(
    BaseHTTPRequestHandler
):
    server_version = (
        "BundleRAGWorker/1.0"
    )

    def log_message(
        self,
        format: str,
        *args,
    ):
        print(
            "[rag-worker] "
            + (
                format
                % args
            ),
            flush=True,
        )

    def _json_response(
        self,
        status: int,
        payload: dict[str, Any],
    ):
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(
                len(
                    body
                )
            ),
        )

        self.end_headers()

        self.wfile.write(
            body
        )

    def do_GET(
        self,
    ):
        if self.path != "/health":
            self._json_response(
                404,
                {
                    "ok": False,
                    "error": "Not found.",
                },
            )
            return

        self._json_response(
            200,
            {
                "ok": True,
                "service": "bundle-rag-worker",
            },
        )

    def do_POST(
        self,
    ):
        if self.path != "/retrieve":
            self._json_response(
                404,
                {
                    "ok": False,
                    "error": "Not found.",
                },
            )
            return

        if not _authorized(
            self.headers
        ):
            self._json_response(
                401,
                {
                    "ok": False,
                    "error": "Unauthorized.",
                },
            )
            return

        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

        except ValueError:
            content_length = 0

        if (
            content_length <= 0
            or content_length
            > MAX_BODY_BYTES
        ):
            self._json_response(
                400,
                {
                    "ok": False,
                    "error": "Invalid request body size.",
                },
            )
            return

        try:
            raw = self.rfile.read(
                content_length
            )

            payload = json.loads(
                raw.decode(
                    "utf-8"
                )
            )

            question = str(
                payload.get(
                    "question",
                    "",
                )
            ).strip()

            role = str(
                payload.get(
                    "role",
                    "",
                )
            ).strip()

            dataset_name = str(
                payload.get(
                    "dataset_name",
                    "",
                )
            ).strip()

            limit = int(
                payload.get(
                    "limit",
                    5,
                )
            )

            if not question:
                raise ValueError(
                    "question is required."
                )

            if role not in {
                "admin",
                "analyst",
                "viewer",
            }:
                raise ValueError(
                    "Invalid role."
                )

            if not dataset_name:
                raise ValueError(
                    "dataset_name is required."
                )

            results = retrieve_allowed_chunks(
                question=question,
                role=role,
                dataset_name=dataset_name,
                limit=limit,
            )

            self._json_response(
                200,
                {
                    "ok": True,
                    "results": (
                        rag_results_to_evidence(
                            results
                        )
                    ),
                },
            )

        except PermissionError as exc:
            self._json_response(
                403,
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                    "error_type": (
                        type(
                            exc
                        ).__name__
                    ),
                },
            )

        except ValueError as exc:
            self._json_response(
                400,
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                    "error_type": (
                        type(
                            exc
                        ).__name__
                    ),
                },
            )

        except Exception as exc:
            self._json_response(
                500,
                {
                    "ok": False,
                    "error": str(
                        exc
                    ),
                    "error_type": (
                        type(
                            exc
                        ).__name__
                    ),
                },
            )


def main():
    print(
        "Starting Bundle persistent RAG worker...",
        flush=True,
    )

    print(
        f"Listening on http://{HOST}:{PORT}",
        flush=True,
    )

    print(
        "FastEmbed will load on the first retrieval "
        "and remain cached for later requests.",
        flush=True,
    )

    server = ThreadingHTTPServer(
        (
            HOST,
            PORT,
        ),
        Handler,
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print(
            "\nStopping RAG worker...",
            flush=True,
        )

    finally:
        server.server_close()


if __name__ == "__main__":
    main()

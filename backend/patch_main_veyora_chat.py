from __future__ import annotations

from pathlib import Path


MAIN_PATH = Path(__file__).resolve().parent / "main.py"

IMPORT_LINE = (
    "from backend.veyora_chat_router import "
    "maybe_process_veyora_chat\n"
)

PROCESS_MARKER = "        result = process_chat(\n"

REPLACEMENT = """        veyora_result = maybe_process_veyora_chat(
            body.message,
            role=current_user.role,
        )

        if veyora_result is not None:
            result = veyora_result
        else:
            result = process_chat(
                body.message,

                history=[
                    item.model_dump()
                    for item in body.history
                ],

                context=(
                    body.context.model_dump()
                    if body.context
                    else None
                ),
            )

"""


def main() -> None:
    original_text = MAIN_PATH.read_text(encoding="utf-8")
    text = original_text

    if (
        "maybe_process_veyora_chat" in text
        and "veyora_result =" in text
    ):
        print("backend/main.py is already patched.")
        return

    if IMPORT_LINE not in text:
        ai_import = "from backend.ai import process_chat\n"

        if ai_import in text:
            text = text.replace(
                ai_import,
                ai_import + IMPORT_LINE,
                1,
            )
        else:
            marker = "# =================================================="

            if marker not in text:
                raise RuntimeError(
                    "Could not find a safe import insertion point. "
                    "No file changes were written."
                )

            text = text.replace(
                marker,
                IMPORT_LINE + "\n" + marker,
                1,
            )

    start = text.find(PROCESS_MARKER)

    if start == -1:
        raise RuntimeError(
            "Could not find the current process_chat call. "
            "No file changes were written."
        )

    end_marker = "        execution_time_ms = int(\n"
    end = text.find(end_marker, start)

    if end == -1:
        raise RuntimeError(
            "Could not find the end of the process_chat block. "
            "No file changes were written."
        )

    text = text[:start] + REPLACEMENT + text[end:]

    backup = MAIN_PATH.with_suffix(".py.before_veyora_chat")

    if not backup.exists():
        backup.write_text(
            original_text,
            encoding="utf-8",
        )

    MAIN_PATH.write_text(
        text,
        encoding="utf-8",
    )

    print("Patched backend/main.py successfully.")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
MAIN_PATH = BACKEND_DIR / "main.py"
BACKUP_PATH = BACKEND_DIR / "main.py.before_veyora_chat"

IMPORT_LINE = (
    "from backend.veyora_chat_router import "
    "maybe_process_veyora_chat\n"
)

LEGACY_MARKER = (
    '        if chat_mode == "legacy":\n'
)

NEW_DISPATCH = (
    "        veyora_result = maybe_process_veyora_chat(\n"
    "            body.message,\n"
    "            role=current_user.role,\n"
    "        )\n"
    "\n"
    "        if veyora_result is not None:\n"
    "            result = veyora_result\n"
    "        elif chat_mode == \"legacy\":\n"
)


def main() -> None:
    if not BACKUP_PATH.exists():
        raise RuntimeError(
            "Missing backend/main.py.before_veyora_chat. "
            "This repair intentionally restores the pre-patch "
            "main.py before applying the safe routing change."
        )

    original = BACKUP_PATH.read_text(
        encoding="utf-8"
    )

    text = original

    if IMPORT_LINE not in text:
        ai_import = (
            "from backend.ai import process_chat\n"
        )

        if ai_import not in text:
            raise RuntimeError(
                "Could not locate the backend.ai process_chat import "
                "in the backup. No changes were written."
            )

        text = text.replace(
            ai_import,
            ai_import + IMPORT_LINE,
            1,
        )

    if LEGACY_MARKER not in text:
        raise RuntimeError(
            'Could not locate `if chat_mode == "legacy":` '
            "in the backup. No changes were written."
        )

    text = text.replace(
        LEGACY_MARKER,
        NEW_DISPATCH,
        1,
    )

    safety_backup = (
        BACKEND_DIR
        / "main.py.before_veyora_chat_repair"
    )

    if not safety_backup.exists():
        safety_backup.write_text(
            MAIN_PATH.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )

    MAIN_PATH.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "Restored original chat flow and applied "
        "safe Veyora routing."
    )
    print(
        f"Repair backup: {safety_backup}"
    )


if __name__ == "__main__":
    main()

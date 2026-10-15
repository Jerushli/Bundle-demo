from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    [
        sys.executable,
        "-m",
        "backend.test_veyora_production_readiness",
    ],
    [
        sys.executable,
        "-m",
        "backend.evaluate_veyora_hybrid_intelligence",
    ],
]


def main() -> None:
    print(
        "Bundle / Veyora Production Readiness Suite"
    )
    print("=" * 68)

    for command in COMMANDS:
        print()
        print(
            "[RUN] "
            + " ".join(command[1:])
        )

        completed = subprocess.run(
            command,
            check=False,
        )

        if completed.returncode != 0:
            raise SystemExit(
                completed.returncode
            )

    print()
    print("=" * 68)
    print(
        "Production readiness suite completed successfully."
    )


if __name__ == "__main__":
    main()

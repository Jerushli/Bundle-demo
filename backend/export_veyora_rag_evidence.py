from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _to_float(value: str | None) -> float:
    if value is None:
        return 0.0

    text = str(value).strip()

    if not text:
        return 0.0

    return float(text.replace(",", ""))


def _to_bool(value: str | None) -> bool:
    text = str(value or "").strip().lower()

    if text in {
        "yes",
        "true",
        "1",
    }:
        return True

    if text in {
        "no",
        "false",
        "0",
    }:
        return False

    raise ValueError(
        f"Unsupported boolean value: {value!r}"
    )


def build_veyora_rag_candidates(
    source_csv: str | Path,
    *,
    dataset_name: str = "veyora_massive",
    access_level: str = "internal",
) -> list[dict[str, Any]]:
    if access_level not in {
        "public",
        "internal",
        "restricted",
    }:
        raise ValueError(
            "access_level must be public, internal, or restricted."
        )

    path = Path(source_csv)

    if not path.exists():
        raise FileNotFoundError(
            str(path)
        )

    aggregates: dict[
        tuple[str, str],
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "event_count": 0,
            "sla_missed_count": 0,
            "downtime_sum": 0.0,
            "profit_sum": 0.0,
        }
    )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        required = {
            "region",
            "manager_notes",
            "sla_met",
            "downtime_hours",
            "profit",
        }

        actual = set(
            reader.fieldnames or []
        )

        missing = (
            required
            - actual
        )

        if missing:
            raise ValueError(
                "Source CSV is missing required columns: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        for row in reader:
            region = str(
                row.get(
                    "region",
                    ""
                )
            ).strip()

            note = str(
                row.get(
                    "manager_notes",
                    ""
                )
            ).strip()

            if not region or not note:
                continue

            key = (
                region,
                note,
            )

            bucket = aggregates[
                key
            ]

            bucket[
                "event_count"
            ] += 1

            if not _to_bool(
                row.get(
                    "sla_met"
                )
            ):
                bucket[
                    "sla_missed_count"
                ] += 1

            bucket[
                "downtime_sum"
            ] += _to_float(
                row.get(
                    "downtime_hours"
                )
            )

            bucket[
                "profit_sum"
            ] += _to_float(
                row.get(
                    "profit"
                )
            )

    candidates: list[
        dict[str, Any]
    ] = []

    for index, (
        (
            region,
            note,
        ),
        bucket,
    ) in enumerate(
        sorted(
            aggregates.items(),
            key=lambda item: (
                item[0][0],
                -item[1][
                    "event_count"
                ],
                item[0][1],
            ),
        ),
        start=1,
    ):
        event_count = int(
            bucket[
                "event_count"
            ]
        )

        missed = int(
            bucket[
                "sla_missed_count"
            ]
        )

        miss_rate = (
            missed
            * 100.0
            / event_count
            if event_count
            else 0.0
        )

        avg_downtime = (
            bucket[
                "downtime_sum"
            ]
            / event_count
            if event_count
            else 0.0
        )

        avg_profit = (
            bucket[
                "profit_sum"
            ]
            / event_count
            if event_count
            else 0.0
        )

        candidate_key = hashlib.sha256(
            (
                f"{dataset_name}"
                f"|{region}"
                f"|{note}"
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        body = (
            f"Region: {region}\n"
            f"Manager note: {note}\n"
            f"Observed in "
            f"{event_count:,} "
            f"service events in "
            f"{region}. "
            f"{missed:,} "
            f"of those events missed SLA "
            f"({miss_rate:.2f}%). "
            f"Average downtime for these "
            f"events is "
            f"{avg_downtime:.2f} hours. "
            f"Average profit is "
            f"{avg_profit:,.2f}. "
            "These are observed associations "
            "in the source data and do not "
            "by themselves prove causation."
        )

        candidates.append(
            {
                "dataset_name": dataset_name,
                "source_row_number": index,
                "source_column": "manager_notes",
                "candidate_key": candidate_key,
                "title": (
                    "Veyora region evidence | "
                    f"{region} | "
                    f"{candidate_key[:12]}"
                ),
                "document_type": (
                    "veyora_region_operational_evidence"
                ),
                "access_level": (
                    access_level
                ),
                "body": body,
            }
        )

    return candidates


def export_veyora_rag_candidates(
    source_csv: str | Path,
    output_path: str | Path,
    *,
    dataset_name: str = "veyora_massive",
    access_level: str = "internal",
) -> dict[str, Any]:
    rows = build_veyora_rag_candidates(
        source_csv,
        dataset_name=dataset_name,
        access_level=access_level,
    )

    output = Path(
        output_path
    )

    with output.open(
        "w",
        encoding="utf-8",
    ) as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )

    region_counts: dict[
        str,
        int,
    ] = {}

    for row in rows:
        first_line = row[
            "body"
        ].splitlines()[0]

        region = (
            first_line
            .replace(
                "Region: ",
                "",
                1,
            )
            .strip()
        )

        region_counts[
            region
        ] = (
            region_counts.get(
                region,
                0,
            )
            + 1
        )

    return {
        "dataset_name": dataset_name,
        "source_csv": str(
            source_csv
        ),
        "output_path": str(
            output
        ),
        "candidate_count": len(
            rows
        ),
        "region_counts": (
            region_counts
        ),
        "access_level": (
            access_level
        ),
        "source_column": (
            "manager_notes"
        ),
        "region_scoped": True,
        "body_prefix_contract": (
            "Region: <region>"
        ),
        "causality_claimed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export region-scoped Veyora "
            "manager-note RAG evidence directly "
            "from the source CSV."
        )
    )

    parser.add_argument(
        "source_csv"
    )

    parser.add_argument(
        "--output",
        default=(
            "veyora_manager_notes_rag_v4.jsonl"
        ),
    )

    parser.add_argument(
        "--dataset-name",
        default=(
            "veyora_massive"
        ),
    )

    parser.add_argument(
        "--access-level",
        default="internal",
        choices=[
            "public",
            "internal",
            "restricted",
        ],
    )

    args = parser.parse_args()

    result = (
        export_veyora_rag_candidates(
            args.source_csv,
            args.output,
            dataset_name=(
                args.dataset_name
            ),
            access_level=(
                args.access_level
            ),
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

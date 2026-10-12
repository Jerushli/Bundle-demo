from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from backend.database import get_database_connection
from backend.mixed_content_detector import analyze_csv_columns


PAIR_PATTERN = re.compile(
    r"""
    (?P<key>[A-Za-z][A-Za-z0-9 _/\-]{0,60})
    \s*[:=]\s*
    (?P<value>.*?)
    (?=
        \s*[,;|]\s*
        [A-Za-z][A-Za-z0-9 _/\-]{0,60}
        \s*[:=]
        |
        $
    )
    """,
    re.VERBOSE,
)


def normalize_field_name(name: str) -> str:
    cleaned = name.strip().lower()

    cleaned = re.sub(
        r"[^a-z0-9]+",
        "_",
        cleaned,
    )

    cleaned = cleaned.strip("_")

    if not cleaned:
        return "field"

    if cleaned[0].isdigit():
        cleaned = (
            "field_"
            + cleaned
        )

    return cleaned[:80]


def extract_key_value_pairs(
    text: str,
) -> dict[str, str]:
    if not text:
        return {}

    result: dict[str, str] = {}

    for match in PAIR_PATTERN.finditer(
        text
    ):
        raw_key = (
            match.group(
                "key"
            )
            or ""
        ).strip()

        raw_value = (
            match.group(
                "value"
            )
            or ""
        ).strip()

        if not raw_key:
            continue

        key = normalize_field_name(
            raw_key
        )

        # Preserve duplicate keys deterministically instead of silently
        # overwriting earlier values.
        if key in result:
            suffix = 2
            candidate = (
                f"{key}_{suffix}"
            )

            while candidate in result:
                suffix += 1
                candidate = (
                    f"{key}_{suffix}"
                )

            key = candidate

        result[
            key
        ] = raw_value

    return result


def _read_csv(
    file_path: str | Path,
) -> tuple[
    Path,
    bytes,
    str,
    csv.Dialect,
    list[str],
    list[dict[str, str]],
]:
    path = Path(
        file_path
    )

    if not path.exists():
        raise ValueError(
            f"File does not exist: {path}"
        )

    if (
        path.suffix.lower()
        != ".csv"
    ):
        raise ValueError(
            "Stage 22.3 currently supports CSV files only."
        )

    raw = path.read_bytes()

    if not raw:
        raise ValueError(
            "CSV file is empty."
        )

    try:
        text = raw.decode(
            "utf-8-sig"
        )

    except UnicodeDecodeError as exc:
        raise ValueError(
            "CSV must currently be UTF-8 encoded."
        ) from exc

    try:
        dialect = csv.Sniffer().sniff(
            text[
                :10000
            ],
            delimiters=",;\t|",
        )

    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(
        text.splitlines(),
        dialect=dialect,
    )

    original_fields = (
        reader.fieldnames
        or []
    )

    fields = [
        (
            field.strip()
            if field
            else ""
        )
        for field in original_fields
    ]

    if not fields:
        raise ValueError(
            "No CSV header row could be detected."
        )

    if any(
        not field
        for field in fields
    ):
        raise ValueError(
            "One or more CSV columns have an empty header."
        )

    rows: list[
        dict[str, str]
    ] = []

    for row in reader:
        normalized: dict[
            str,
            str,
        ] = {}

        for original, clean_name in zip(
            original_fields,
            fields,
        ):
            normalized[
                clean_name
            ] = str(
                row.get(
                    original
                )
                or ""
            ).strip()

        rows.append(
            normalized
        )

    if not rows:
        raise ValueError(
            "CSV has headers but no data rows."
        )

    return (
        path,
        raw,
        text,
        dialect,
        fields,
        rows,
    )


def extract_structured_candidates(
    file_path: str | Path,
    *,
    columns: list[str] | None = None,
    sample_rows: int = 5000,
) -> dict[str, Any]:
    (
        path,
        raw,
        _text,
        dialect,
        fields,
        rows,
    ) = _read_csv(
        file_path
    )

    if sample_rows < 1:
        raise ValueError(
            "sample_rows must be at least 1."
        )

    analysis = analyze_csv_columns(
        path,
        sample_rows=min(
            sample_rows,
            5000,
        ),
    )

    by_name = {
        item[
            "column_name"
        ]: item
        for item in analysis[
            "columns"
        ]
    }

    if columns is None:
        selected_columns = [
            name
            for name in analysis[
                "routing"
            ][
                "extraction_columns"
            ]
        ]

    else:
        selected_columns = [
            column.strip()
            for column in columns
            if column.strip()
        ]

    if not selected_columns:
        raise ValueError(
            "No extraction-required columns were detected or selected."
        )

    missing = [
        column
        for column in selected_columns
        if column not in fields
    ]

    if missing:
        raise ValueError(
            "Unknown extraction column(s): "
            + ", ".join(
                missing
            )
        )

    records: list[
        dict[str, Any]
    ] = []

    field_counter: Counter[
        str
    ] = Counter()

    successful_rows = 0
    attempted_rows = 0

    for row_number, row in enumerate(
        rows[
            :sample_rows
        ],
        start=1,
    ):
        for column in selected_columns:
            raw_text = row.get(
                column,
                "",
            ).strip()

            if not raw_text:
                continue

            attempted_rows += 1

            fields_found = (
                extract_key_value_pairs(
                    raw_text
                )
            )

            if fields_found:
                successful_rows += 1

                field_counter.update(
                    fields_found.keys()
                )

            records.append(
                {
                    "source_row_number": row_number,
                    "source_column": column,
                    "raw_text": raw_text,
                    "extraction_status": (
                        "candidate_extracted"
                        if fields_found
                        else "no_supported_pattern"
                    ),
                    "fields": fields_found,
                }
            )

    discovered_fields = []

    denominator = max(
        successful_rows,
        1,
    )

    for field_name, count in sorted(
        field_counter.items()
    ):
        discovered_fields.append(
            {
                "field_name": field_name,
                "rows_present": count,
                "presence_ratio": round(
                    count
                    / denominator,
                    4,
                ),
            }
        )

    success_ratio = (
        successful_rows
        / attempted_rows
        if attempted_rows
        else 0.0
    )

    warnings: list[str] = []

    for column in selected_columns:
        metadata = by_name.get(
            column,
            {},
        )

        if (
            metadata.get(
                "extraction_required"
            )
            is not True
        ):
            warnings.append(
                f"Column '{column}' was manually selected but Stage 22.2 "
                "did not mark it extraction_required."
            )

    if success_ratio < 0.80:
        warnings.append(
            "Extraction success is below 80%; Stage 22.4 validation and "
            "human review should treat this result conservatively."
        )

    return {
        "source": "text_to_structured_extraction",
        "extractor_version": "22.3",
        "filename": path.name,
        "sha256": hashlib.sha256(
            raw
        ).hexdigest(),
        "file_size_bytes": len(
            raw
        ),
        "delimiter": getattr(
            dialect,
            "delimiter",
            ",",
        ),
        "selected_columns": selected_columns,
        "source_row_count": len(
            rows
        ),
        "attempted_text_cells": attempted_rows,
        "successful_extractions": successful_rows,
        "extraction_success_ratio": round(
            success_ratio,
            4,
        ),
        "candidate_record_count": len(
            records
        ),
        "discovered_fields": discovered_fields,
        "warnings": warnings,
        "records": records,
        "status": (
            "candidates_ready_for_validation"
            if successful_rows
            else "no_candidates_extracted"
        ),
        "next_stage": (
            "22.4_deterministic_validation"
        ),
    }


def persist_extraction_run(
    result: dict[str, Any],
    *,
    dataset_name: str | None = None,
    analysis_id: int | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    query = """
        INSERT INTO bundle.text_extraction_runs (
            dataset_name,
            analysis_id,
            filename,
            file_sha256,
            extractor_version,
            selected_columns,
            attempted_text_cells,
            successful_extractions,
            extraction_success_ratio,
            candidate_record_count,
            discovered_fields,
            result_json,
            created_by,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s::jsonb, %s, %s, %s,
            %s, %s::jsonb, %s::jsonb,
            %s, NOW()
        )
        RETURNING
            id AS extraction_run_id,
            created_at
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    dataset_name,
                    analysis_id,
                    result[
                        "filename"
                    ],
                    result[
                        "sha256"
                    ],
                    result[
                        "extractor_version"
                    ],
                    json.dumps(
                        result[
                            "selected_columns"
                        ]
                    ),
                    result[
                        "attempted_text_cells"
                    ],
                    result[
                        "successful_extractions"
                    ],
                    result[
                        "extraction_success_ratio"
                    ],
                    result[
                        "candidate_record_count"
                    ],
                    json.dumps(
                        result[
                            "discovered_fields"
                        ]
                    ),
                    json.dumps(
                        result
                    ),
                    created_by,
                ),
            )

            row = cursor.fetchone()

        connection.commit()

    return {
        **result,
        "extraction_run_id": row[
            "extraction_run_id"
        ],
        "persisted_at": row[
            "created_at"
        ],
    }


def list_extraction_runs(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    safe_limit = max(
        1,
        min(
            int(
                limit
            ),
            200,
        ),
    )

    query = """
        SELECT
            id AS extraction_run_id,
            dataset_name,
            analysis_id,
            filename,
            file_sha256,
            extractor_version,
            selected_columns,
            attempted_text_cells,
            successful_extractions,
            extraction_success_ratio,
            candidate_record_count,
            discovered_fields,
            result_json,
            created_by,
            created_at
        FROM bundle.text_extraction_runs
        ORDER BY id DESC
        LIMIT %s
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                (
                    safe_limit,
                ),
            )

            rows = cursor.fetchall()

    return {
        "source": "text_to_structured_extraction",
        "runs": rows,
    }


from __future__ import annotations
import csv, hashlib, json, re, time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from psycopg import sql
from psycopg.rows import dict_row
from backend.database import get_database_connection
from backend.mixed_content_detector import analyze_csv_columns

def _safe_name(value: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    x = re.sub(r"_+", "_", x) or "dataset"
    return ("c_" + x if x[0].isdigit() else x)[:55]

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _pg_type(kind: str) -> str:
    return {
        "numeric": "DOUBLE PRECISION",
        "date": "DATE",
        "boolean": "BOOLEAN",
    }.get(kind, "TEXT")

def _convert(value: str | None, kind: str) -> Any:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if kind == "numeric":
        return float(Decimal(text.replace(",", "")))
    if kind == "date":
        return date.fromisoformat(text)
    if kind == "boolean":
        low = text.lower()
        if low in {"yes", "true", "1"}:
            return True
        if low in {"no", "false", "0"}:
            return False
        raise ValueError(f"Invalid boolean: {text}")
    return text

def stream_csv_to_analytics(
    file_path: str | Path,
    *,
    dataset_name: str,
    sample_rows: int = 5000,
    batch_size: int = 10000,
    created_by: str | None = None,
) -> dict[str, Any]:
    path = Path(file_path)
    started = time.perf_counter()
    analysis = analyze_csv_columns(path, sample_rows=sample_rows)

    names = analysis["routing"]["analytics_columns"]
    lookup = {c["column_name"]: c for c in analysis["columns"]}
    cols = [lookup[n] for n in names if n in lookup]
    if not cols:
        raise ValueError("No analytics columns detected.")

    sha = _sha256_file(path)
    schema_name = "analytics"
    table_name = f"massive_{_safe_name(dataset_name)}_{sha[:8]}"

    with get_database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema_name)))
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
                sql.Identifier(schema_name), sql.Identifier(table_name)
            ))

            defs = [
                sql.SQL("{} {}").format(
                    sql.Identifier(c["column_name"]),
                    sql.SQL(_pg_type(c["semantic_type"]))
                )
                for c in cols
            ]
            defs += [
                sql.SQL("_bundle_source_row BIGINT NOT NULL"),
                sql.SQL("_bundle_source_file TEXT NOT NULL"),
                sql.SQL("_bundle_source_sha256 TEXT NOT NULL"),
                sql.SQL("_bundle_loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"),
            ]
            cur.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
                sql.SQL(", ").join(defs),
            ))

            copy_cols = [c["column_name"] for c in cols] + [
                "_bundle_source_row", "_bundle_source_file", "_bundle_source_sha256"
            ]
            copy_sql = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
                sql.SQL(", ").join(sql.Identifier(x) for x in copy_cols),
            )

            inserted = rejected = batches = pending = 0
            rejection_examples = []

            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                with cur.copy(copy_sql) as cp:
                    for row_num, row in enumerate(reader, start=1):
                        try:
                            values = [
                                _convert(row.get(c["column_name"]), c["semantic_type"])
                                for c in cols
                            ]
                            values += [row_num, path.name, sha]
                            cp.write_row(values)
                            inserted += 1
                            pending += 1
                        except Exception as exc:
                            rejected += 1
                            if len(rejection_examples) < 10:
                                rejection_examples.append({
                                    "source_row_number": row_num,
                                    "error": str(exc),
                                })
                        if pending >= batch_size:
                            batches += 1
                            pending = 0
                    if pending:
                        batches += 1

        duration = round(time.perf_counter() - started, 3)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO bundle.massive_data_stream_loads (
                    dataset_name, source_filename, source_sha256,
                    analytics_schema, analytics_table,
                    detected_analytics_columns,
                    inserted_rows, rejected_rows,
                    batch_size, batch_count, duration_seconds,
                    status, created_by, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,NOW())
                RETURNING id AS load_id
                """,
                (
                    dataset_name, path.name, sha, schema_name, table_name,
                    json.dumps([c["column_name"] for c in cols]),
                    inserted, rejected, batch_size, batches, duration,
                    "completed" if rejected == 0 else "completed_with_rejections",
                    created_by,
                ),
            )
            load_id = cur.fetchone()["load_id"]
        conn.commit()

    return {
        "source": "massive_data_streaming_loader",
        "load_id": load_id,
        "dataset_name": dataset_name,
        "analytics_schema": schema_name,
        "analytics_table": table_name,
        "analytics_column_count": len(cols),
        "analytics_columns": [c["column_name"] for c in cols],
        "excluded_rag_columns": analysis["routing"].get("rag_columns", []),
        "excluded_extraction_columns": analysis["routing"].get("extraction_columns", []),
        "inserted_rows": inserted,
        "rejected_rows": rejected,
        "batch_size": batch_size,
        "batch_count": batches,
        "duration_seconds": duration,
        "status": "completed" if rejected == 0 else "completed_with_rejections",
        "rejection_examples": rejection_examples,
        "guardrails": {
            "active_dataset_changed": False,
            "rag_vector_write_performed": False,
            "embedded_structure_loaded_as_duplicate_numeric_truth": False,
            "giant_intermediate_json_created": False,
        },
    }

def verify_streamed_table(*, schema_name: str, table_name: str) -> dict[str, Any]:
    with get_database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql.SQL("""
                SELECT
                    COUNT(*) AS row_count,
                    MIN(event_date) AS min_date,
                    MAX(event_date) AS max_date,
                    SUM(revenue) AS total_revenue,
                    SUM(profit) AS total_profit,
                    AVG(downtime_hours) AS avg_downtime_hours
                FROM {}.{}
            """).format(sql.Identifier(schema_name), sql.Identifier(table_name)))
            row = cur.fetchone()
    return {"schema": schema_name, "table": table_name, "summary": dict(row)}

from __future__ import annotations
import csv, hashlib, json, re
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
from psycopg.rows import dict_row
from backend.database import get_database_connection

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y")
BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "0", "1"}
NUMBER_RE = re.compile(r"^[+-]?(?:₹|\$|€|£)?\s*(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?(?:\s*%)?$")
KV_RE = re.compile(r"[A-Za-z][A-Za-z0-9 _/\-]{1,40}\s*[:=]\s*[^,;|]+")

def _clean(v: Any) -> str:
    return "" if v is None else str(v).strip()

def _is_number(v: str) -> bool:
    return bool(v and NUMBER_RE.fullmatch(v.strip()))

def _is_date(v: str) -> bool:
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(v.strip(), fmt)
            return True
        except ValueError:
            pass
    return False

def _is_boolean(v: str) -> bool:
    return v.strip().lower() in BOOLEAN_VALUES

def _has_embedded(v: str) -> bool:
    return len(KV_RE.findall(v)) >= 2 if v else False

def _sentence_like(v: str) -> bool:
    return len(v) >= 40 and len(v.split()) >= 8 and sum(v.count(x) for x in ".!?;:") >= 1

def _analyze_column(name: str, values: list[str]) -> dict[str, Any]:
    total = len(values)
    non = [v for v in values if v]
    n = len(non)
    if n == 0:
        return {
            "column_name": name, "semantic_type": "empty", "analytics_eligible": False,
            "rag_candidate": False, "extraction_required": False, "review_required": False,
            "sample_count": total, "non_empty_count": 0, "null_ratio": 1.0,
            "numeric_ratio": 0.0, "date_ratio": 0.0, "boolean_ratio": 0.0,
            "embedded_structure_ratio": 0.0, "sentence_like_ratio": 0.0,
            "long_text_ratio": 0.0, "distinct_ratio": 0.0,
            "average_length": 0.0, "max_length": 0,
            "reason": "Column has no sampled non-empty values."
        }
    num = sum(_is_number(v) for v in non) / n
    dat = sum(_is_date(v) for v in non) / n
    boo = sum(_is_boolean(v) for v in non) / n
    emb = sum(_has_embedded(v) for v in non) / n
    sent = sum(_sentence_like(v) for v in non) / n
    lng = sum(len(v) >= 80 for v in non) / n
    distinct = len(set(non)) / n
    avg = mean(len(v) for v in non)
    mx = max(len(v) for v in non)
    typ, analytics, rag, extraction, review = "short_text", True, False, False, False
    reason = "Short textual values are suitable for structured storage."
    if num >= 0.80:
        typ, reason = "numeric", "Most sampled values are numeric."
    elif dat >= 0.80:
        typ, reason = "date", "Most sampled values match supported date formats."
    elif boo >= 0.80:
        typ, reason = "boolean", "Most sampled values behave like boolean values."
    elif emb >= 0.35:
        typ, analytics, rag, extraction = "embedded_structure", False, True, True
        reason = "Repeated key:value patterns indicate multiple facts embedded inside text."
    elif lng >= 0.50 or sent >= 0.50:
        typ, analytics, rag = "free_text", False, True
        reason = "Most sampled values contain narrative or sentence-like text."
    elif max(num, dat, boo, emb, sent, lng) >= 0.25:
        typ, analytics, rag, extraction, review = "mixed", False, True, emb >= 0.20, True
        reason = "Multiple competing content patterns require review."
    elif avg <= 60 and distinct <= 0.50:
        typ, reason = "categorical", "Short repeated values are suitable for categorical analytics."
    elif avg > 60:
        typ, analytics, rag = "free_text", False, True
        reason = "Text length suggests narrative content."
    return {
        "column_name": name, "semantic_type": typ, "analytics_eligible": analytics,
        "rag_candidate": rag, "extraction_required": extraction, "review_required": review,
        "sample_count": total, "non_empty_count": n,
        "null_ratio": round((total-n)/total, 4) if total else 1.0,
        "numeric_ratio": round(num,4), "date_ratio": round(dat,4), "boolean_ratio": round(boo,4),
        "embedded_structure_ratio": round(emb,4), "sentence_like_ratio": round(sent,4),
        "long_text_ratio": round(lng,4), "distinct_ratio": round(distinct,4),
        "average_length": round(avg,2), "max_length": mx, "reason": reason,
    }

def _routing(columns: list[dict[str, Any]]) -> dict[str, Any]:
    analytics = [c["column_name"] for c in columns if c["analytics_eligible"]]
    rag = [c["column_name"] for c in columns if c["rag_candidate"]]
    extraction = [c["column_name"] for c in columns if c["extraction_required"]]
    review = [c["column_name"] for c in columns if c["review_required"]]
    empty = [c["column_name"] for c in columns if c["semantic_type"] == "empty"]
    if review:
        route = "human_review_before_routing"
    elif extraction:
        route = "extract_embedded_structure_then_split"
    elif analytics and rag:
        route = "split_structured_and_rag"
    elif rag:
        route = "rag_only"
    else:
        route = "structured_only"
    return {
        "file_route": route, "analytics_columns": analytics, "rag_columns": rag,
        "extraction_columns": extraction, "review_columns": review, "empty_columns": empty,
        "analytics_column_count": len(analytics), "rag_column_count": len(rag),
        "extraction_column_count": len(extraction), "review_column_count": len(review),
    }

def analyze_csv_columns(file_path: str | Path, *, sample_rows: int = 500) -> dict[str, Any]:
    p = Path(file_path)
    if not p.exists():
        raise ValueError(f"File does not exist: {p}")
    if p.suffix.lower() != ".csv":
        raise ValueError("Stage 22.2 currently supports CSV files only.")
    raw = p.read_bytes()
    if not raw:
        raise ValueError("CSV file is empty.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must currently be UTF-8 encoded.") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:10000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    original = reader.fieldnames or []
    fields = [(x or "").strip() for x in original]
    if not fields:
        raise ValueError("No CSV header row could be detected.")
    if any(not x for x in fields):
        raise ValueError("One or more CSV columns have an empty header.")
    values = {f: [] for f in fields}
    sampled = 0
    for row in reader:
        if sampled >= sample_rows:
            break
        sampled += 1
        for o, f in zip(original, fields):
            values[f].append(_clean(row.get(o)))
    if sampled == 0:
        raise ValueError("CSV has headers but no data rows.")
    columns = [_analyze_column(f, values[f]) for f in fields]
    return {
        "source": "mixed_content_detector", "detector_version": "22.2", "filename": p.name,
        "sha256": hashlib.sha256(raw).hexdigest(), "file_size_bytes": len(raw),
        "delimiter": getattr(dialect, "delimiter", ","), "sampled_rows": sampled,
        "sample_limit": sample_rows, "column_count": len(columns),
        "routing": _routing(columns), "columns": columns,
    }

def persist_column_analysis(result: dict[str, Any], *, dataset_name: str | None = None, classification_id: int | None = None, created_by: str | None = None) -> dict[str, Any]:
    query = """
        INSERT INTO bundle.input_column_analyses (
            dataset_name, classification_id, filename, file_sha256, detector_version,
            file_route, sampled_rows, column_count, analysis_json, created_by, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,NOW())
        RETURNING id AS analysis_id, created_at
    """
    with get_database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (
                dataset_name, classification_id, result["filename"], result["sha256"],
                result["detector_version"], result["routing"]["file_route"],
                result["sampled_rows"], result["column_count"], json.dumps(result), created_by,
            ))
            row = cur.fetchone()
        conn.commit()
    return {**result, "analysis_id": row["analysis_id"], "persisted_at": row["created_at"]}

def list_column_analyses(*, limit: int = 50) -> dict[str, Any]:
    safe = max(1, min(int(limit), 200))
    query = """
        SELECT id AS analysis_id, dataset_name, classification_id, filename, file_sha256,
               detector_version, file_route, sampled_rows, column_count, analysis_json,
               created_by, created_at
        FROM bundle.input_column_analyses
        ORDER BY id DESC LIMIT %s
    """
    with get_database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (safe,))
            rows = cur.fetchall()
    return {"source": "mixed_content_detector", "analyses": rows}

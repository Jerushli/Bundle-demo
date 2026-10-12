
from __future__ import annotations
import csv, hashlib, json, re
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
from psycopg.rows import dict_row
from backend.database import get_database_connection

DATE_FORMATS = ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%Y/%m/%d","%m/%d/%Y")
NUM_RE = re.compile(r"^[+-]?(?:₹|\$|€|£)?\s*(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?(?:\s*%)?$")
KV_RE = re.compile(r"[A-Za-z][A-Za-z0-9 _/\-]{1,40}\s*[:=]\s*[^,;|]+")

def _is_number(v:str)->bool:
    return bool(v and NUM_RE.fullmatch(v.strip()))

def _is_date(v:str)->bool:
    v=v.strip()
    for f in DATE_FORMATS:
        try:
            datetime.strptime(v,f); return True
        except ValueError:
            pass
    return False

def _kv(v:str)->bool:
    return len(KV_RE.findall(v)) >= 2

def _profile(name:str, values:list[str])->dict[str,Any]:
    vals=[v.strip() for v in values if v is not None]
    non=[v for v in vals if v]
    n=len(vals); nn=len(non)
    if nn:
        num=sum(_is_number(v) for v in non)/nn
        dat=sum(_is_date(v) for v in non)/nn
        lng=sum(len(v)>=80 for v in non)/nn
        kv=sum(_kv(v) for v in non)/nn
        avg=mean(len(v) for v in non); mx=max(len(v) for v in non)
    else:
        num=dat=lng=kv=avg=0.0; mx=0
    if nn==0: kind="empty"
    elif num>=0.80: kind="numeric"
    elif dat>=0.80: kind="date"
    elif kv>=0.35: kind="embedded_structure"
    elif lng>=0.50: kind="long_text"
    elif max(num,dat,lng,kv)>=0.25: kind="mixed"
    else: kind="short_text"
    return {
        "column_name":name,
        "sample_count":n,
        "non_empty_count":nn,
        "null_ratio":round((n-nn)/n,4) if n else 1.0,
        "numeric_ratio":round(num,4),
        "date_ratio":round(dat,4),
        "long_text_ratio":round(lng,4),
        "key_value_ratio":round(kv,4),
        "average_length":round(avg,2),
        "max_length":mx,
        "inferred_kind":kind,
    }

def _classify(cols:list[dict[str,Any]]):
    usable=[c for c in cols if c["inferred_kind"]!="empty"]
    if not usable:
        return "invalid",1.0,"reject_or_review",["No non-empty data columns were found."]
    structured={"numeric","date","short_text"}
    text={"long_text","embedded_structure"}
    sc=sum(c["inferred_kind"] in structured for c in usable)
    tc=sum(c["inferred_kind"] in text for c in usable)
    mc=sum(c["inferred_kind"]=="mixed" for c in usable)
    total=len(usable)
    maxkv=max(c["key_value_ratio"] for c in usable)
    maxlong=max(c["long_text_ratio"] for c in usable)
    if total==1 and (tc==1 or maxkv>=0.35 or maxlong>=0.50):
        return "unstructured",0.95,"text_extraction_required",[
            "The CSV is physically tabular, but the sampled content is concentrated in one text-heavy or embedded-structure column."
        ]
    if sc>=1 and (tc>=1 or mc>=1):
        return "mixed",0.90,"mixed_content_analysis",[
            "The sample combines ordinary structured columns with text-heavy, embedded-structure, or mixed-content columns."
        ]
    if tc/total>=0.60:
        return "unstructured",0.90,"text_extraction_required",[
            "Most sampled columns are long-form text or contain embedded key:value content."
        ]
    if sc/total>=0.70:
        return "structured",0.95,"existing_structured_pipeline",[
            "Most sampled columns behave like normal numeric, date, or short categorical fields."
        ]
    return "mixed",0.70,"mixed_content_analysis",[
        "The file contains ambiguous column behavior and should enter mixed-content analysis."
    ]

def classify_csv_file(file_path:str|Path, *, sample_rows:int=200)->dict[str,Any]:
    p=Path(file_path)
    if not p.exists(): raise ValueError(f"File does not exist: {p}")
    if p.suffix.lower()!=".csv": raise ValueError("Stage 22.1 currently supports CSV files only.")
    raw=p.read_bytes()
    if not raw:
        return {"source":"input_file_classifier","classifier_version":"22.1","filename":p.name,
                "file_size_bytes":0,"sha256":hashlib.sha256(raw).hexdigest(),
                "classification":"invalid","confidence":1.0,"recommended_route":"reject_or_review",
                "reasoning":["The file is empty."],"sampled_rows":0,"column_count":0,"columns":[]}
    try: text=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise ValueError("CSV must currently be UTF-8 encoded.") from exc
    try: dialect=csv.Sniffer().sniff(text[:10000], delimiters=",;\t|")
    except csv.Error: dialect=csv.excel
    reader=csv.DictReader(text.splitlines(), dialect=dialect)
    fields=[(x or "").strip() for x in (reader.fieldnames or [])]
    if not fields: raise ValueError("No CSV header row could be detected.")
    if any(not x for x in fields): raise ValueError("One or more CSV columns have an empty header.")
    values={f:[] for f in fields}; count=0
    for row in reader:
        if count>=sample_rows: break
        count+=1
        for original, clean in zip(reader.fieldnames or [], fields):
            values[clean].append(str(row.get(original) or "").strip())
    if count==0: raise ValueError("CSV has headers but no data rows.")
    cols=[_profile(f,values[f]) for f in fields]
    cls,conf,route,reasons=_classify(cols)
    return {
        "source":"input_file_classifier","classifier_version":"22.1","filename":p.name,
        "file_size_bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
        "delimiter":getattr(dialect,"delimiter",","),"classification":cls,
        "confidence":conf,"recommended_route":route,"reasoning":reasons,
        "sampled_rows":count,"sample_limit":sample_rows,"column_count":len(cols),"columns":cols,
    }

def persist_classification(result:dict[str,Any], *, dataset_name:str|None=None, created_by:str|None=None):
    with get_database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
            INSERT INTO bundle.input_file_classifications
            (dataset_name,filename,file_sha256,file_size_bytes,classifier_version,
             classification,confidence,recommended_route,sampled_rows,column_count,
             result_json,created_by,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,NOW())
            RETURNING id AS classification_id, created_at
            """,(dataset_name,result["filename"],result["sha256"],result["file_size_bytes"],
                 result["classifier_version"],result["classification"],result["confidence"],
                 result["recommended_route"],result["sampled_rows"],result["column_count"],
                 json.dumps(result),created_by))
            row=cur.fetchone()
        conn.commit()
    return {**result,"classification_id":row["classification_id"],"persisted_at":row["created_at"]}

def list_classifications(*, limit:int=50):
    limit=max(1,min(int(limit),200))
    with get_database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
            SELECT id AS classification_id,dataset_name,filename,file_sha256,file_size_bytes,
                   classifier_version,classification,confidence,recommended_route,sampled_rows,
                   column_count,result_json,created_by,created_at
            FROM bundle.input_file_classifications
            ORDER BY id DESC LIMIT %s
            """,(limit,))
            rows=cur.fetchall()
    return {"source":"input_file_classifier","classifications":rows}

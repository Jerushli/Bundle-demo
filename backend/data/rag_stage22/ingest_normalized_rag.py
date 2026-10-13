
from __future__ import annotations
import argparse, hashlib, json, os
from datetime import date
from pathlib import Path
import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"
ALLOWED={"public","internal","restricted"}

def load_rows(path:Path):
    rows=[]
    with path.open("r",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():
                continue
            obj=json.loads(line)
            access=str(obj.get("access_level","")).strip()
            if access not in ALLOWED:
                raise ValueError(f"Line {i}: invalid access_level '{access}'.")
            if not str(obj.get("title","")).strip():
                raise ValueError(f"Line {i}: empty title.")
            if not str(obj.get("body","")).strip():
                raise ValueError(f"Line {i}: empty body.")
            rows.append(obj)
    return rows

def inspect_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
        SELECT column_name,data_type,is_nullable,column_default
        FROM information_schema.columns
        WHERE table_schema='rag' AND table_name='documents'
        ORDER BY ordinal_position
        """)
        rows=cur.fetchall()
    if not rows:
        raise RuntimeError("rag.documents does not exist.")
    return {r[0]:{"data_type":r[1],"is_nullable":r[2],"column_default":r[3]} for r in rows}

def assert_schema(schema):
    required={"id","title","document_type","doc_date","department","country","priority",
              "status","access_level","project_id","customer_id","employee_id",
              "control_id","body"}
    missing=sorted(required-set(schema))
    if missing:
        raise RuntimeError("Missing rag.documents columns: "+", ".join(missing))

def assert_embeddings(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('rag.document_embeddings')")
        if cur.fetchone()[0] is None:
            raise RuntimeError("rag.document_embeddings does not exist.")

def stable_id(obj):
    key=str(obj.get("candidate_key","")).strip()
    if key:
        return "NORM-"+key[:24].upper()
    raw="|".join(str(obj.get(k,"")) for k in
                 ("dataset_name","source_sha256","source_row_number","source_column","body"))
    return "NORM-"+hashlib.sha256(raw.encode()).hexdigest()[:24].upper()

def roles(access):
    if access=="public":
        return ["admin","analyst","viewer"]
    if access=="internal":
        return ["admin","analyst"]
    return ["admin"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("jsonl_path")
    p.add_argument("--department",required=True)
    p.add_argument("--country",required=True)
    p.add_argument("--priority",required=True)
    p.add_argument("--status",required=True)
    p.add_argument("--project-id",required=True)
    p.add_argument("--customer-id",required=True)
    p.add_argument("--employee-id",required=True)
    p.add_argument("--control-id",required=True)
    p.add_argument("--doc-date",required=True)
    p.add_argument("--dry-run",action="store_true")
    a=p.parse_args()

    path=Path(a.jsonl_path)
    if not path.exists():
        raise SystemExit(f"JSONL file not found: {path}")

    try:
        doc_date=date.fromisoformat(a.doc_date)
    except ValueError as exc:
        raise SystemExit("--doc-date must use YYYY-MM-DD") from exc

    rows=load_rows(path)
    print(f"Validated {len(rows)} Stage 22.7 RAG candidate(s).")
    print("Metadata profile:")
    for k,v in {
        "department":a.department,"country":a.country,"priority":a.priority,
        "status":a.status,"project_id":a.project_id,"customer_id":a.customer_id,
        "employee_id":a.employee_id,"control_id":a.control_id,
        "doc_date":doc_date.isoformat()
    }.items():
        print(f"  {k}={v}")

    if a.dry_run:
        print("Dry run complete. No RAG database writes performed.")
        return

    url=os.getenv("RAG_DATABASE_URL")
    if not url:
        raise SystemExit("RAG_DATABASE_URL is required. Do not point it at bundle_new.")

    print("Loading existing FastEmbed MiniLM model...")
    model=TextEmbedding(model_name=MODEL_NAME)
    print("Embedding model ready.")

    mapping=[]
    with psycopg.connect(url) as conn:
        register_vector(conn)
        assert_schema(inspect_schema(conn))
        assert_embeddings(conn)

        with conn.cursor() as cur:
            for obj in rows:
                doc_id=stable_id(obj)
                title=str(obj["title"]).strip()
                body=str(obj["body"]).strip()
                document_type=str(obj.get("document_type","normalized_csv_context")).strip()
                access=str(obj["access_level"]).strip()
                dataset_name=str(obj.get("dataset_name","")).strip() or None
                allowed_roles=roles(access)

                cur.execute("""
                INSERT INTO rag.documents (
                    id,title,document_type,doc_date,department,country,priority,status,
                    access_level,project_id,customer_id,employee_id,control_id,body,
                    dataset_name,allowed_roles
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title,
                    document_type=EXCLUDED.document_type,
                    doc_date=EXCLUDED.doc_date,
                    department=EXCLUDED.department,
                    country=EXCLUDED.country,
                    priority=EXCLUDED.priority,
                    status=EXCLUDED.status,
                    access_level=EXCLUDED.access_level,
                    project_id=EXCLUDED.project_id,
                    customer_id=EXCLUDED.customer_id,
                    employee_id=EXCLUDED.employee_id,
                    control_id=EXCLUDED.control_id,
                    body=EXCLUDED.body,
                    dataset_name=EXCLUDED.dataset_name,
                    allowed_roles=EXCLUDED.allowed_roles
                """,(doc_id,title,document_type,doc_date,a.department,a.country,a.priority,
                     a.status,access,a.project_id,a.customer_id,a.employee_id,a.control_id,
                     body,dataset_name,allowed_roles))

                vector=list(model.embed([f"{title}. {body}"]))[0].tolist()
                cur.execute("""
                INSERT INTO rag.document_embeddings (document_id,model_name,embedding)
                VALUES (%s,%s,%s)
                ON CONFLICT (document_id) DO UPDATE SET
                    model_name=EXCLUDED.model_name,
                    embedding=EXCLUDED.embedding,
                    created_at=NOW()
                """,(doc_id,MODEL_NAME,vector))

                mapping.append({
                    "queue_id":obj.get("queue_id"),
                    "candidate_key":obj.get("candidate_key"),
                    "document_id":doc_id,
                    "access_level":access,
                    "allowed_roles":allowed_roles,
                })
        conn.commit()

    mapping_path=path.with_suffix(".ingested.json")
    mapping_path.write_text(json.dumps({
        "model_name":MODEL_NAME,
        "ingested_count":len(mapping),
        "documents":mapping,
        "metadata_profile":{
            "department":a.department,
            "country":a.country,
            "priority":a.priority,
            "status":a.status,
            "project_id":a.project_id,
            "customer_id":a.customer_id,
            "employee_id":a.employee_id,
            "control_id":a.control_id,
            "doc_date":doc_date.isoformat(),
        }
    },indent=2),encoding="utf-8")

    print(f"Ingested {len(mapping)} document(s).")
    print(f"Mapping written to: {mapping_path}")

if __name__=="__main__":
    main()

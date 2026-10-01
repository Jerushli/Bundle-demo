"""Fast streaming load to PostgreSQL via psycopg 3 COPY. No vectors are created."""
import argparse, gzip, json, os, time
from pathlib import Path

FIELDS=('id','title','type','date','department','country','priority','status','access_level','project_id','customer_id','employee_id','control_id','body')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=Path('data/company_docs'))
    p.add_argument('--limit',type=int,default=10000,help='0 to load all')
    a=p.parse_args()
    url=os.getenv('DATABASE_URL')
    if not url: raise SystemExit('DATABASE_URL missing. Set it in PowerShell with $env:DATABASE_URL=... (do not commit it).')
    try: import psycopg
    except ImportError: raise SystemExit('Install driver: pip install "psycopg[binary]"')
    paths=sorted(a.data.glob('company_docs_*.jsonl.gz'))
    if not paths: raise SystemExit(f'No shards found in {a.data}')
    t=time.monotonic(); count=0
    with psycopg.connect(url) as conn:
        # Minimal insert list explicit; use COPY binary-protocol-safe row interface.
        cols='id,title,document_type,doc_date,department,country,priority,status,access_level,project_id,customer_id,employee_id,control_id,body'
        with conn.cursor() as cur:
            with cur.copy(f'COPY rag.documents ({cols}) FROM STDIN') as cp:
                for path in paths:
                    with gzip.open(path,'rt',encoding='utf8') as f:
                        for line in f:
                            doc=json.loads(line)
                            cp.write_row(tuple(doc[k] for k in FIELDS))
                            count+=1
                            if count%100000==0: print(f'Loaded {count:,} docs',flush=True)
                            if a.limit and count>=a.limit: break
                    if a.limit and count>=a.limit: break
    print(f'Loaded {count:,} docs in {time.monotonic()-t:.1f}s')

if __name__=='__main__': main()

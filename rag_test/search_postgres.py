"""Quick text-search latency baseline; replace with authorized hybrid/vector retrieval for actual RAG."""
import argparse, os, time

def main():
    p=argparse.ArgumentParser()
    p.add_argument('query')
    p.add_argument('--limit',type=int,default=5)
    p.add_argument('--access',choices=['public','internal','restricted'],default='public',help='Demo visibility ceiling, NOT authentication')
    a=p.parse_args()
    try: import psycopg
    except ImportError: raise SystemExit('pip install "psycopg[binary]"')
    url=os.getenv('DATABASE_URL')
    if not url: raise SystemExit('DATABASE_URL environment variable required')
    permitted={'public':('public',),'internal':('public','internal'),'restricted':('public','internal','restricted')}[a.access]
    start=time.perf_counter()
    with psycopg.connect(url) as db:
        with db.cursor() as cur:
            cur.execute('''SELECT id,title,department,access_level,
                           ts_rank_cd(search_vector,websearch_to_tsquery('english',%s)) AS rank
                           FROM rag.documents
                           WHERE access_level=ANY(%s)
                             AND search_vector @@ websearch_to_tsquery('english',%s)
                           ORDER BY rank DESC, id ASC LIMIT %s''',
                           (a.query,list(permitted),a.query,max(1,min(a.limit,20))))
            rows=cur.fetchall()
    print(f'Query: {a.query!r}, results: {len(rows)}, total time: {(time.perf_counter()-start)*1000:.2f} ms')
    for row in rows: print(row)
    print('NOTE: This is keyword/full-text retrieval only, not semantic vector search. --access is a test parameter, not authentication.')

if __name__=='__main__': main()

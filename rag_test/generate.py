"""Generate deterministic, fictional enterprise RAG records. Python 3.10+ standard library."""
import argparse, gzip, hashlib, json, time
from pathlib import Path
from datetime import date, timedelta

COMPANY='COMPANY — Fictional Enterprise Test Data'
DEPARTMENTS=('Finance','People Operations','Engineering','Sales','Operations','Legal','Customer Success','Security','Procurement','Analytics')
COUNTRIES=('India','Germany','Canada','France','United States','Mexico','United Kingdom','Singapore')
DOC_TYPES=('incident_report','support_case','vendor_review','project_update','audit_evidence','sales_meeting','maintenance_log','procurement_note','training_record','risk_assessment')
PRIORITIES=('low','medium','high','critical')
STATUSES=('open','in_progress','resolved','closed','awaiting_review')
TOPICS=('invoice mismatch','payment gateway timeout','warehouse reconciliation','supplier contract renewal','employee onboarding','quarterly forecasting','data quality validation','access review','customer escalation','shipment delay','API latency','inventory discrepancy')
ACTIONS=('validated source records','assigned an accountable owner','escalated to the relevant team','documented the root cause','scheduled a follow-up review','updated the operating checklist','requested independent verification','opened a corrective-action ticket')
CONTROL_IDS=('CTRL-FIN-01','CTRL-SEC-02','CTRL-OPS-03','CTRL-HR-04','CTRL-PRC-05','CTRL-ENG-06')
START=date(2023,1,1)

def make_record(i):
    # Reproducible arithmetic mixing; ensures identifier-level uniqueness without huge RAM.
    dep=DEPARTMENTS[(i*7 + i//37)%len(DEPARTMENTS)]
    country=COUNTRIES[(i*3+i//29)%len(COUNTRIES)]
    kind=DOC_TYPES[(i*11+i//17)%len(DOC_TYPES)]
    topic=TOPICS[(i*13+i//31)%len(TOPICS)]
    status=STATUSES[(i+i//19)%len(STATUSES)]
    priority=PRIORITIES[(i//13+i)%len(PRIORITIES)]
    action=ACTIONS[(i*5+i//7)%len(ACTIONS)]
    control=CONTROL_IDS[(i+i//103)%len(CONTROL_IDS)]
    dt=START+timedelta(days=(i*13+i//101)%1280)
    pid=f'PRJ-{(i*37)%2400+1:05d}'
    cid=f'CUST-{(i*29)%40000+1:06d}'
    vendor=f'VEN-{(i*17)%5000+1:05d}'
    eid=f'EMP-{(i*23)%12000+1:06d}'
    owner=f'Team {(i*7)%83+1:02d}'
    doc_id=f'DOC-{i:08d}'
    access=('public','internal','restricted')[(i*7+i//23)%3]
    # A fictional, document-like narrative with retrieval-relevant factual metadata.
    body=(f'{doc_id} is a {kind.replace("_"," ")} for {dep} in {country}, dated {dt.isoformat()}. '
          f'Topic: {topic}. Priority: {priority}; current status: {status}. '
          f'Project {pid}, customer {cid}, vendor {vendor}, employee {eid}, responsible {owner}. '
          f'Observed case reference CASE-{i:08d} during review; the response team {action}. '
          f'Control reference {control}; next evidence review cycle {(i%90)+1} days. '
          f'Follow-up must preserve the source document ID and respect the {access} access classification. '
          f'Generated synthetic record; not evidence of a real event.')
    return {'id':doc_id,'company':'COMPANY','type':kind,'title':f'{kind.replace("_"," ").title()} | {topic.title()} | {doc_id}',
            'date':dt.isoformat(),'department':dep,'country':country,'priority':priority,
            'status':status,'access_level':access,'project_id':pid,'customer_id':cid,
            'employee_id':eid,'control_id':control,'body':body}

def generate(out, count, shard_size):
    out.mkdir(parents=True, exist_ok=True)
    manifest={'dataset':'COMPANY Synthetic Enterprise RAG','fictional':True,'record_count':count,
              'shard_size':shard_size,'schema_version':1,'shards':[]}
    tick=time.monotonic()
    for first in range(1,count+1,shard_size):
        last=min(first+shard_size-1,count)
        name=f'company_docs_{first:08d}_{last:08d}.jsonl.gz'
        path=out/name
        # gzip mtime 0 permits reproducible data within version/runtime.
        with path.open('wb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=5,mtime=0) as gz:
                for i in range(first,last+1):
                    gz.write((json.dumps(make_record(i),separators=(',',':'),ensure_ascii=False)+'\n').encode('utf-8'))
        digest=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
        manifest['shards'].append({'file':name,'count':last-first+1,'sha256':digest.hexdigest(), 'compressed_bytes':path.stat().st_size})
        print(f'{last:,}/{count:,} records | {name} | {path.stat().st_size/1048576:.1f} MiB',flush=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print(f'COMPLETE: {count:,} documents across {len(manifest["shards"])} shards in {time.monotonic()-tick:.1f}s')

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Generate COMPANY synthetic RAG documents')
    p.add_argument('--count',type=int,default=10000)
    p.add_argument('--shard-size',type=int,default=100000)
    p.add_argument('--out',type=Path,default=Path('data/company_docs'))
    a=p.parse_args()
    if a.count<1 or a.shard_size<1: p.error('count and shard-size must be positive')
    generate(a.out,a.count,a.shard_size)

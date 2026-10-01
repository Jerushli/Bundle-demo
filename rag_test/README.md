# Bundle RAG synthetic COMPANY benchmark

## What's in these downloads

- `COMPANY_RAG_Starter.zip`: Python standard-library generator, 24 curated fictional policy Markdown files, SQL schema, PostgreSQL streaming loader, lexical search baseline, and 10 benchmark questions. A 10,000-record preview is included.
- `COMPANY_RAG_1_Million_Documents.zip`: ten `.jsonl.gz` shards containing **1,000,000 distinct ID-addressable, structured, synthetic operational documents** and `manifest.json`. Each line is one document with a narrative `body` and structured metadata. The document narratives are *template-generated*, not one million unique authored policies. For semantic quality evaluation, use the curated policies and build additional labeled queries; volume alone measures scalability rather than real-world answer quality.

Everything is fictional. No genuine employee/customer records, and no dependency on your `financials` table. Reconcile data IDs before adding database joins. Dataset record dates are 2023-2026, while your Financials CSV covers 2013-2014; **do not present them as the same business reporting period**.

## Windows setup (PowerShell, project root)

1. Extract the starter zip into a new folder, e.g., `Bundle-demo/rag_test`.
2. Extract the one-million zip into `Bundle-demo/rag_test/data/company_docs/`. Make sure `manifest.json` is directly in that folder beside `company_docs_*.jsonl.gz`.
3. First verify a small preview with the built-in library:

```powershell
python -c "import gzip,json; p='rag_test/data/company_docs/company_docs_00000001_00100000.jsonl.gz'; f=gzip.open(p,'rt',encoding='utf8'); print(json.loads(next(f)))"
```

4. Make a **separate PostgreSQL test database**, e.g., `bundle_rag_test`, in pgAdmin 4 (right-click Databases → Create → Database). In Query Tool on that database, run `rag_test/sql/01_create_rag_documents.sql`. Do not paste SQL into the terminal.
5. Install the PostgreSQL driver in your project virtual environment:

```powershell
pip install "psycopg[binary]"
```

6. Set the URL **only in the current PowerShell shell**, targeting the test database:

```powershell
$env:DATABASE_URL="postgresql://YOUR_USER:YOUR_PASSWORD@localhost:5432/bundle_rag_test"
```

If your password includes `@`, `#`, `/`, `:` etc., URL-encode it. Never publish `.env`, credentials, or passwords.

7. Start with **10,000** to verify permissions/throughput (test table is initially empty):

```powershell
python rag_test/load_postgres.py --data rag_test/data/company_docs --limit 10000
```

8. Run a lexical retrieval baseline:

```powershell
python rag_test/search_postgres.py "payment gateway timeout" --access public
```

9. For full load, use an **empty table** to avoid primary-key duplicates. In pgAdmin run `TRUNCATE TABLE rag.documents;` in the dedicated test DB, then:

```powershell
python rag_test/load_postgres.py --data rag_test/data/company_docs --limit 0
```

10. Check count:

```sql
SELECT COUNT(*) FROM rag.documents;
SELECT department, COUNT(*) FROM rag.documents GROUP BY department ORDER BY department;
```

Expected: 1,000,000 rows. Exact file counts and sha256 checksums are in `manifest.json`.

## Regenerate any size without extra libraries

From the starter folder:

```powershell
python generate.py --count 10000 --shard-size 10000 --out data/company_docs
python generate.py --count 1000000 --shard-size 100000 --out data/company_docs
```

## RAG engineering notes

**Phase A**: Load and search 10,000 docs; test ACL enforcement and source references. **Phase B**: Load all 1,000,000 docs and measure ingest rate, database size, keyword top-k latency and p95 latency. **Phase C**: Add a real embedding model and pgvector collection/index; benchmark semantic recall on labeled queries. **Phase D**: Hybrid search + rerank + grounded answer generation with source `id`, applying back-end user-specific permissions *before* sending passages to an LLM.

The included `search_postgres.py` uses **PostgreSQL full-text search only**, **not embeddings or RAG**. The `--access` switch is a convenience test simulation, **not secure user authentication**. Never expose that CLI mechanism directly to end users. Do not permit the LLM to issue unrestricted SQL. Store immutable document/chunk IDs and embedding model version.

**Performance benchmarks**: ingestion documents/second; disk size (`pg_total_relation_size('rag.documents')`); top-k p50/p95 over 100+ varied queries; retrieval recall@5/10; fraction of answers with correct document citations; unauthorized retrieval rate (target zero). CPU-only embedding one million records can take a long time; start small and batch.

**Important**: the operational data is procedurally repetitive; nearly-identical wording across documents can make semantic retrieval artificially hard or deceptively easy depending on evaluation. Treat it as an ingestion and filtering stress fixture. The policy directory and benchmark question file provide a small, manually aligned correctness fixture.

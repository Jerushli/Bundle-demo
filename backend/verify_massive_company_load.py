
import argparse, json
from backend.streaming_company_loader import verify_streamed_table

p = argparse.ArgumentParser()
p.add_argument("--schema", default="analytics")
p.add_argument("--table", required=True)
a = p.parse_args()

print(json.dumps(
    verify_streamed_table(schema_name=a.schema, table_name=a.table),
    indent=2,
    default=str,
))

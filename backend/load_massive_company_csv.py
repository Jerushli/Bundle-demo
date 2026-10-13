
import argparse, json
from backend.streaming_company_loader import stream_csv_to_analytics

p = argparse.ArgumentParser()
p.add_argument("file_path")
p.add_argument("--dataset-name", required=True)
p.add_argument("--sample-rows", type=int, default=5000)
p.add_argument("--batch-size", type=int, default=10000)
a = p.parse_args()

result = stream_csv_to_analytics(
    a.file_path,
    dataset_name=a.dataset_name,
    sample_rows=a.sample_rows,
    batch_size=a.batch_size,
    created_by="cli",
)
print(json.dumps(result, indent=2, default=str))

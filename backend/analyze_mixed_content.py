import argparse, json
from backend.mixed_content_detector import analyze_csv_columns, persist_column_analysis

def main():
    p = argparse.ArgumentParser()
    p.add_argument("file_path")
    p.add_argument("--sample-rows", type=int, default=500)
    p.add_argument("--dataset-name")
    p.add_argument("--classification-id", type=int)
    p.add_argument("--persist", action="store_true")
    a = p.parse_args()
    result = analyze_csv_columns(a.file_path, sample_rows=a.sample_rows)
    if a.persist:
        result = persist_column_analysis(result, dataset_name=a.dataset_name, classification_id=a.classification_id, created_by="cli")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()

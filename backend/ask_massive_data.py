from __future__ import annotations
import argparse, json
from backend.massive_data_intelligence import ask_massive_dataset

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--dataset-name", default="veyora_massive")
    args = parser.parse_args()

    result = ask_massive_dataset(
        args.question,
        dataset_name=args.dataset_name,
    )
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()

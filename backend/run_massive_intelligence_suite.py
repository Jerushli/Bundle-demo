from __future__ import annotations
import json
import time
from backend.massive_data_intelligence import ask_massive_dataset

QUESTIONS = [
    "What is total revenue?",
    "What is total profit?",
    "Which region generated the most revenue?",
    "Which service type has the highest profit margin?",
    "What percentage of service events missed SLA?",
    "Which region has the highest average downtime hours?",
    "Show the monthly revenue trend over time.",
]

def main() -> None:
    all_results = []

    for question in QUESTIONS:
        started = time.perf_counter()
        result = ask_massive_dataset(
            question,
            dataset_name="veyora_massive",
        )
        elapsed_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        print()
        print("QUESTION:", question)
        print("ANSWER:", result.get("answer"))
        print("QUERY TIME MS:", elapsed_ms)

        all_results.append({
            "question": question,
            "answer": result.get("answer"),
            "query_time_ms": elapsed_ms,
            "operation": result.get("operation"),
        })

    print()
    print("=" * 60)
    print("Massive data intelligence test suite completed.")
    print(json.dumps(all_results, indent=2))

if __name__ == "__main__":
    main()

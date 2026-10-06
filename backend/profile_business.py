import argparse
import json
from pathlib import Path

from backend.business_profiler import (
    profile_business_dataset,
    profile_to_dict,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate Bundle business metrics and a "
            "quick executive summary from a clean analytics table."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset name used during ingestion.",
    )

    parser.add_argument(
        "--primary-measure",
        help=(
            "Optional validated measure to use as the "
            "main ranking metric, e.g. sales or profit."
        ),
    )

    parser.add_argument(
        "--output",
        help="Optional JSON output path.",
    )

    args = parser.parse_args()

    profile = profile_business_dataset(
        args.dataset,
        primary_measure_override=(
            args.primary_measure
        ),
    )

    print()
    print("Bundle business profile")
    print("-----------------------")
    print(
        f"Dataset:         {profile.dataset_name}"
    )
    print(
        f"Analytics table: {profile.analytics_table}"
    )
    print(
        f"Rows:            {profile.total_rows:,}"
    )
    print(
        f"Primary measure: {profile.primary_measure or 'none'}"
    )

    print()
    print("Quick executive summary")
    print("-----------------------")
    print(
        profile.quick_summary
    )

    print()
    print("Measures")
    print("--------")

    for measure in profile.measures:
        print(
            f"{measure.column_name}: "
            f"total={measure.total}, "
            f"avg={measure.average}, "
            f"min={measure.minimum}, "
            f"max={measure.maximum}"
        )

    print()
    print("Suggested questions")
    print("-------------------")

    for question in profile.suggested_questions:
        print(
            f"- {question}"
        )

    if args.output:
        output = Path(
            args.output
        ).expanduser().resolve()

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            json.dumps(
                profile_to_dict(
                    profile
                ),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print()
        print(
            f"JSON profile written to: {output}"
        )


if __name__ == "__main__":
    main()

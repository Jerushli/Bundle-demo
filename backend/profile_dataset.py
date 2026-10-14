import argparse
import json
from pathlib import Path

from backend.schema_profiler import (
    profile_dataset,
    profile_to_dict,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Profile a Bundle raw staging dataset "
            "and infer likely schema roles."
        )
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help=(
            "Dataset name used during ingestion, "
            "for example bundle_test_sales."
        ),
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=50_000,
        help=(
            "Maximum rows loaded into memory for profiling. "
            "Default: 50000."
        ),
    )

    parser.add_argument(
        "--output",
        help=(
            "Optional JSON file path for the generated profile."
        ),
    )

    args = parser.parse_args()

    profile = profile_dataset(
        dataset_name=args.dataset,
        sample_size=args.sample_size,
    )

    data = profile_to_dict(
        profile
    )

    print()
    print("Bundle schema profile")
    print("---------------------")
    print(
        f"Dataset:       {profile.dataset_name}"
    )
    print(
        f"Staging table: {profile.staging_table}"
    )
    print(
        f"Total rows:    {profile.total_rows:,}"
    )
    print(
        f"Sample rows:   {profile.sample_rows:,}"
    )
    print(
        f"Columns:       {profile.column_count}"
    )

    print()
    print("Detected columns")
    print("----------------")

    for column in profile.columns:
        rag_label = (
            " | RAG candidate"
            if column.rag_candidate
            else ""
        )

        print(
            f"{column.column_name}: "
            f"{column.likely_type} / "
            f"{column.likely_role} "
            f"(confidence={column.confidence:.2f}, "
            f"null={column.null_rate:.1%})"
            f"{rag_label}"
        )

    print()
    print("Summary")
    print("-------")

    for key, value in profile.summary.items():
        print(f"{key}: {value}")

    if args.output:
        output_path = Path(
            args.output
        ).expanduser().resolve()

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print()
        print(
            f"JSON profile written to: {output_path}"
        )


if __name__ == "__main__":
    main()

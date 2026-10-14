import argparse
import json
from pathlib import Path

from backend.dataset_validator import (
    report_to_dict,
    validate_dataset,
)


def main():
    parser = argparse.ArgumentParser(
        description="Validate a Bundle Stage 2 profile before transformation."
    )

    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset name used during ingestion.",
    )

    parser.add_argument(
        "--sample-limit",
        type=int,
        default=50_000,
        help="Rows checked in sample mode. Default: 50000.",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Validate all rows instead of a sample.",
    )

    parser.add_argument(
        "--output",
        help="Optional JSON report path.",
    )

    args = parser.parse_args()

    report = validate_dataset(
        args.dataset,
        full_validation=args.full,
        sample_limit=args.sample_limit,
    )

    print()
    print("Bundle validation report")
    print("------------------------")
    print(f"Dataset: {report.dataset_name}")
    print(f"Rows:    {report.total_rows:,}")
    print(f"Mode:    {report.validation_mode}")
    print(
        "Ready:   "
        + ("YES" if report.ready_for_transform else "NO")
    )

    print()
    print("Columns")
    print("-------")

    for column in report.columns:
        status = "SAFE" if column.conversion_safe else "REVIEW"

        extra = ""
        if column.duplicate_rows is not None:
            extra = f", duplicates={column.duplicate_rows}"

        print(
            f"{column.column_name}: "
            f"{column.proposed_type} / {column.proposed_role} "
            f"-> {status} "
            f"(invalid={column.invalid_rows}{extra})"
        )

        for warning in column.warnings:
            print(f"  - {warning}")

    if report.warnings:
        print()
        print("Dataset warnings")
        print("----------------")
        for warning in report.warnings:
            print(f"- {warning}")

    print()
    print("Proposed PostgreSQL schema")
    print("--------------------------")
    print(report.proposed_schema_sql)

    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                report_to_dict(report),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print()
        print(f"JSON report written to: {output}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from backend.daily_intelligence import (
    get_active_dataset,
    get_available_columns,
    list_kpi_definitions,
)


def main() -> None:
    print("Stage 21.1 smoke test")
    print("=" * 50)

    active = get_active_dataset()

    print("Active dataset:", active.dataset_name)
    print("Analytics table:", active.analytics_table)

    columns = get_available_columns()

    print(
        "Available columns:",
        len(columns["columns"]),
    )

    kpis = list_kpi_definitions(
        include_disabled=True
    )

    print(
        "Configured KPIs:",
        len(kpis["kpis"]),
    )

    print("Stage 21.1 smoke test passed.")


if __name__ == "__main__":
    main()

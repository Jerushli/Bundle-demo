from __future__ import annotations

import re
from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from backend.database import get_database_connection


ALLOWED_METRICS = {
    "revenue",
    "profit",
    "cogs",
    "units_serviced",
    "unit_price",
    "discount_pct",
    "downtime_hours",
    "customer_satisfaction",
}

ALLOWED_DIMENSIONS = {
    "region",
    "city",
    "client_segment",
    "fleet_type",
    "service_type",
    "service_plan",
    "sales_channel",
    "sla_met",
    "repeat_service",
}


def _resolve_table(dataset_name: str) -> dict[str, Any]:
    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id AS load_id,
                    dataset_name,
                    analytics_schema,
                    analytics_table,
                    inserted_rows,
                    rejected_rows,
                    created_at
                FROM bundle.massive_data_stream_loads
                WHERE dataset_name = %s
                  AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (dataset_name,),
            )
            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"No completed massive-data load exists for '{dataset_name}'."
        )

    return dict(row)


def get_total(
    dataset_name: str,
    *,
    metric: str,
) -> dict[str, Any]:
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    target = _resolve_table(dataset_name)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    "SELECT COUNT(*) AS row_count, "
                    "SUM({metric}) AS total_value "
                    "FROM {schema}.{table}"
                ).format(
                    metric=sql.Identifier(metric),
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                )
            )
            row = cursor.fetchone()

    return {
        "operation": "total",
        "dataset_name": dataset_name,
        "metric": metric,
        "row_count": row["row_count"],
        "value": float(row["total_value"] or 0),
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def get_average(
    dataset_name: str,
    *,
    metric: str,
) -> dict[str, Any]:
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    target = _resolve_table(dataset_name)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    "SELECT COUNT(*) AS row_count, "
                    "AVG({metric}) AS average_value "
                    "FROM {schema}.{table}"
                ).format(
                    metric=sql.Identifier(metric),
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                )
            )
            row = cursor.fetchone()

    return {
        "operation": "average",
        "dataset_name": dataset_name,
        "metric": metric,
        "row_count": row["row_count"],
        "value": float(row["average_value"] or 0),
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def get_group_ranking(
    dataset_name: str,
    *,
    metric: str,
    group_by: str,
    aggregation: str = "sum",
    limit: int = 10,
) -> dict[str, Any]:
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    if group_by not in ALLOWED_DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {group_by}")

    if aggregation not in {"sum", "avg"}:
        raise ValueError("Aggregation must be sum or avg.")

    safe_limit = max(1, min(int(limit), 50))
    target = _resolve_table(dataset_name)

    agg = sql.SQL("SUM") if aggregation == "sum" else sql.SQL("AVG")

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT
                        {group_by}::text AS group_name,
                        COUNT(*) AS row_count,
                        {agg}({metric}) AS value
                    FROM {schema}.{table}
                    GROUP BY {group_by}
                    ORDER BY value DESC NULLS LAST
                    LIMIT %s
                    """
                ).format(
                    group_by=sql.Identifier(group_by),
                    agg=agg,
                    metric=sql.Identifier(metric),
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                ),
                (safe_limit,),
            )
            rows = cursor.fetchall()

    return {
        "operation": "group_ranking",
        "dataset_name": dataset_name,
        "metric": metric,
        "group_by": group_by,
        "aggregation": aggregation,
        "rows": [
            {
                "group_name": row["group_name"],
                "row_count": row["row_count"],
                "value": float(row["value"] or 0),
            }
            for row in rows
        ],
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def get_profit_margin_by_group(
    dataset_name: str,
    *,
    group_by: str,
    limit: int = 10,
) -> dict[str, Any]:
    if group_by not in ALLOWED_DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {group_by}")

    target = _resolve_table(dataset_name)
    safe_limit = max(1, min(int(limit), 50))

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT
                        {group_by}::text AS group_name,
                        COUNT(*) AS row_count,
                        SUM(revenue) AS revenue,
                        SUM(profit) AS profit,
                        CASE
                            WHEN SUM(revenue) = 0 THEN NULL
                            ELSE SUM(profit) * 100.0 / SUM(revenue)
                        END AS profit_margin_pct
                    FROM {schema}.{table}
                    GROUP BY {group_by}
                    ORDER BY profit_margin_pct DESC NULLS LAST
                    LIMIT %s
                    """
                ).format(
                    group_by=sql.Identifier(group_by),
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                ),
                (safe_limit,),
            )
            rows = cursor.fetchall()

    return {
        "operation": "profit_margin",
        "dataset_name": dataset_name,
        "group_by": group_by,
        "rows": [
            {
                "group_name": row["group_name"],
                "row_count": row["row_count"],
                "revenue": float(row["revenue"] or 0),
                "profit": float(row["profit"] or 0),
                "profit_margin_pct": (
                    float(row["profit_margin_pct"])
                    if row["profit_margin_pct"] is not None
                    else None
                ),
            }
            for row in rows
        ],
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def get_sla_miss_rate(
    dataset_name: str,
) -> dict[str, Any]:
    target = _resolve_table(dataset_name)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT
                        COUNT(*) AS total_events,
                        COUNT(*) FILTER (WHERE sla_met = FALSE) AS missed_events,
                        COUNT(*) FILTER (WHERE sla_met = TRUE) AS met_events,
                        CASE
                            WHEN COUNT(*) = 0 THEN 0
                            ELSE
                                COUNT(*) FILTER (WHERE sla_met = FALSE)
                                * 100.0 / COUNT(*)
                        END AS miss_rate_pct
                    FROM {schema}.{table}
                    """
                ).format(
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                )
            )
            row = cursor.fetchone()

    return {
        "operation": "sla_miss_rate",
        "dataset_name": dataset_name,
        "total_events": row["total_events"],
        "missed_events": row["missed_events"],
        "met_events": row["met_events"],
        "miss_rate_pct": float(row["miss_rate_pct"] or 0),
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def get_monthly_trend(
    dataset_name: str,
    *,
    metric: str,
) -> dict[str, Any]:
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    target = _resolve_table(dataset_name)

    with get_database_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    SELECT
                        DATE_TRUNC('month', event_date)::date AS month,
                        COUNT(*) AS row_count,
                        SUM({metric}) AS value
                    FROM {schema}.{table}
                    GROUP BY 1
                    ORDER BY 1
                    """
                ).format(
                    metric=sql.Identifier(metric),
                    schema=sql.Identifier(target["analytics_schema"]),
                    table=sql.Identifier(target["analytics_table"]),
                )
            )
            rows = cursor.fetchall()

    return {
        "operation": "monthly_trend",
        "dataset_name": dataset_name,
        "metric": metric,
        "rows": [
            {
                "month": str(row["month"]),
                "row_count": row["row_count"],
                "value": float(row["value"] or 0),
            }
            for row in rows
        ],
        "table": f'{target["analytics_schema"]}.{target["analytics_table"]}',
    }


def ask_massive_dataset(
    question: str,
    *,
    dataset_name: str,
) -> dict[str, Any]:
    q = re.sub(r"\s+", " ", question.strip().lower())

    metric = None
    for candidate in (
        "revenue",
        "profit",
        "cogs",
        "downtime_hours",
        "customer_satisfaction",
        "units_serviced",
    ):
        label = candidate.replace("_", " ")
        if label in q:
            metric = candidate
            break

    dimension = None
    aliases = {
        "region": "region",
        "city": "city",
        "segment": "client_segment",
        "fleet": "fleet_type",
        "service type": "service_type",
        "service": "service_type",
        "service plan": "service_plan",
        "channel": "sales_channel",
    }

    for phrase, column in sorted(
        aliases.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if phrase in q:
            dimension = column
            break

    if "sla" in q and any(
        phrase in q
        for phrase in ("miss", "failure", "failed", "not met", "percentage")
    ):
        result = get_sla_miss_rate(dataset_name)
        result["answer"] = (
            f"{result['missed_events']:,} of {result['total_events']:,} "
            f"service events missed SLA, a miss rate of "
            f"{result['miss_rate_pct']:.2f}%."
        )
        return result

    if "profit margin" in q or "margin" in q:
        group_by = dimension or "service_type"
        result = get_profit_margin_by_group(
            dataset_name,
            group_by=group_by,
            limit=10,
        )
        first = result["rows"][0] if result["rows"] else None
        result["answer"] = (
            f"{first['group_name']} has the highest {group_by.replace('_', ' ')} "
            f"profit margin at {first['profit_margin_pct']:.2f}%."
            if first
            else "No matching data was found."
        )
        return result

    if any(x in q for x in ("monthly", "trend", "over time")):
        metric = metric or "revenue"
        result = get_monthly_trend(dataset_name, metric=metric)
        result["answer"] = (
            f"Returned {len(result['rows'])} monthly {metric} observations "
            "from deterministic PostgreSQL data."
        )
        return result

    if "average" in q or "avg" in q:
        metric = metric or "downtime_hours"
        if dimension:
            result = get_group_ranking(
                dataset_name,
                metric=metric,
                group_by=dimension,
                aggregation="avg",
                limit=10,
            )
            first = result["rows"][0] if result["rows"] else None
            result["answer"] = (
                f"{first['group_name']} has the highest average "
                f"{metric.replace('_', ' ')} at {first['value']:.2f}."
                if first
                else "No matching data was found."
            )
            return result

        result = get_average(dataset_name, metric=metric)
        result["answer"] = (
            f"Average {metric.replace('_', ' ')} is {result['value']:.2f}."
        )
        return result

    if dimension and metric:
        result = get_group_ranking(
            dataset_name,
            metric=metric,
            group_by=dimension,
            aggregation="sum",
            limit=10,
        )
        first = result["rows"][0] if result["rows"] else None
        result["answer"] = (
            f"{first['group_name']} ranks first by {metric} with "
            f"{first['value']:,.2f}."
            if first
            else "No matching data was found."
        )
        return result

    if metric:
        result = get_total(dataset_name, metric=metric)
        result["answer"] = (
            f"Total {metric.replace('_', ' ')} is {result['value']:,.2f} "
            f"across {result['row_count']:,} records."
        )
        return result

    raise ValueError(
        "Question is not yet supported by the deterministic massive-data test router."
    )

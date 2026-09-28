from datetime import date

from psycopg.rows import dict_row

from backend.database import get_database_connection


# ============================================================
# EXISTING ORDER REPORTING TOOL
# ============================================================

def get_order_summary(
    from_date: str,
    to_date: str,
    group_by: str = "total",
    provider: str | None = None
):
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)

    if start > end:
        raise ValueError(
            "The start date cannot be after the end date."
        )

    if (end - start).days > 30:
        raise ValueError(
            "The selected date range cannot exceed 31 days."
        )

    allowed_groups = [
        "total",
        "provider",
        "date"
    ]

    if group_by not in allowed_groups:
        raise ValueError(
            "Invalid grouping option."
        )

    filters = """
        WHERE o.order_date >= %s
        AND o.order_date <= %s
    """

    parameters = [start, end]

    if provider:
        filters += """
            AND p.provider_name = %s
        """

        parameters.append(provider)

    if group_by == "total":
        query = f"""
            SELECT
                COUNT(o.order_id) AS total_orders
            FROM orders o
            JOIN providers p
                ON o.provider_id = p.provider_id
            {filters}
        """

    elif group_by == "provider":
        query = f"""
            SELECT
                p.provider_name,
                COUNT(o.order_id) AS total_orders
            FROM orders o
            JOIN providers p
                ON o.provider_id = p.provider_id
            {filters}
            GROUP BY p.provider_name
            ORDER BY p.provider_name
        """

    else:
        query = f"""
            SELECT
                o.order_date,
                COUNT(o.order_id) AS total_orders
            FROM orders o
            JOIN providers p
                ON o.provider_id = p.provider_id
            {filters}
            GROUP BY o.order_date
            ORDER BY o.order_date
        """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                parameters
            )

            rows = cursor.fetchall()

    for row in rows:
        if isinstance(
            row.get("order_date"),
            date
        ):
            row["order_date"] = (
                row["order_date"].isoformat()
            )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "group_by": group_by,
        "provider": provider,
        "rows": rows
    }


# ============================================================
# NEW FINANCIAL REPORTING TOOL
# ============================================================

def get_financial_summary(
    metric: str = "sales",
    group_by: str = "total",
    year: int | None = None,
    country: str | None = None,
    product: str | None = None,
    segment: str | None = None,
    limit: int = 20
):
    """
    Analyze the local PostgreSQL financials table.

    Supported metrics:
        sales
        profit
        cogs
        gross_sales
        discounts
        units_sold

    Supported groupings:
        total
        country
        product
        segment
        year
        month
        discount_band
    """

    allowed_metrics = {
        "sales": "sales",
        "profit": "profit",
        "cogs": "cogs",
        "gross_sales": "gross_sales",
        "discounts": "discounts",
        "units_sold": "units_sold"
    }

    allowed_groups = {
        "total": None,
        "country": "country",
        "product": "product",
        "segment": "segment",
        "year": "year",
        "month": "month_name",
        "discount_band": "discount_band"
    }

    if metric not in allowed_metrics:
        raise ValueError(
            f"Invalid metric: {metric}"
        )

    if group_by not in allowed_groups:
        raise ValueError(
            f"Invalid grouping option: {group_by}"
        )

    if limit < 1:
        limit = 1

    if limit > 100:
        limit = 100

    metric_column = allowed_metrics[metric]
    group_column = allowed_groups[group_by]

    filters = []
    parameters = []

    if year is not None:
        filters.append("year = %s")
        parameters.append(year)

    if country:
        filters.append(
            "LOWER(country) = LOWER(%s)"
        )
        parameters.append(country)

    if product:
        filters.append(
            "LOWER(product) = LOWER(%s)"
        )
        parameters.append(product)

    if segment:
        filters.append(
            "LOWER(segment) = LOWER(%s)"
        )
        parameters.append(segment)

    where_clause = ""

    if filters:
        where_clause = (
            "WHERE " + " AND ".join(filters)
        )

    if group_by == "total":
        query = f"""
            SELECT
                COALESCE(
                    SUM({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
        """

    elif group_by == "month":
        query = f"""
            SELECT
                month_name AS group_name,
                month_number,
                COALESCE(
                    SUM({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
            GROUP BY
                month_name,
                month_number
            ORDER BY
                month_number
            LIMIT %s
        """

        parameters.append(limit)

    else:
        query = f"""
            SELECT
                {group_column} AS group_name,
                COALESCE(
                    SUM({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
            GROUP BY {group_column}
            ORDER BY value DESC
            LIMIT %s
        """

        parameters.append(limit)

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:
            cursor.execute(
                query,
                parameters
            )

            rows = cursor.fetchall()

    return {
        "metric": metric,
        "group_by": group_by,
        "filters": {
            "year": year,
            "country": country,
            "product": product,
            "segment": segment
        },
        "rows": rows
    }


def get_financial_comparison(
    metric: str,
    group_by: str,
    values: list[str],
    year: int | None = None
):
    allowed_metrics = {
        "sales": "sales",
        "profit": "profit",
        "cogs": "cogs",
        "gross_sales": "gross_sales",
        "discounts": "discounts",
        "units_sold": "units_sold",
    }

    allowed_groups = {
        "country": "country",
        "product": "product",
        "segment": "segment",
        "discount_band": "discount_band",
    }

    if metric not in allowed_metrics:
        raise ValueError(
            f"Invalid metric: {metric}"
        )

    if group_by not in allowed_groups:
        raise ValueError(
            f"Invalid comparison group: {group_by}"
        )

    if not values:
        raise ValueError(
            "At least one comparison value is required."
        )

    metric_column = allowed_metrics[metric]
    group_column = allowed_groups[group_by]

    filters = []
    parameters = []

    placeholders = ", ".join(
        ["%s"] * len(values)
    )

    filters.append(
        f"LOWER({group_column}) IN ("
        + ", ".join(
            ["LOWER(%s)"] * len(values)
        )
        + ")"
    )

    parameters.extend(values)

    if year is not None:
        filters.append("year = %s")
        parameters.append(year)

    where_clause = (
        "WHERE " + " AND ".join(filters)
    )

    query = f"""
        SELECT
            {group_column} AS group_name,
            COALESCE(
                SUM({metric_column}),
                0
            ) AS value
        FROM financials
        {where_clause}
        GROUP BY {group_column}
        ORDER BY value DESC
    """

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:

            cursor.execute(
                query,
                parameters
            )

            rows = cursor.fetchall()

    return {
        "metric": metric,
        "group_by": group_by,
        "values": values,
        "year": year,
        "rows": rows,
    }

def get_percentage_of_total(
    metric: str,
    group_by: str,
    value: str,
    year: int | None = None
):
    allowed_metrics = {
        "sales": "sales",
        "profit": "profit",
        "cogs": "cogs",
        "gross_sales": "gross_sales",
        "discounts": "discounts",
        "units_sold": "units_sold",
    }

    allowed_groups = {
        "country": "country",
        "product": "product",
        "segment": "segment",
        "discount_band": "discount_band",
    }

    if metric not in allowed_metrics:
        raise ValueError(
            f"Invalid metric: {metric}"
        )

    if group_by not in allowed_groups:
        raise ValueError(
            f"Invalid grouping: {group_by}"
        )

    metric_column = allowed_metrics[metric]
    group_column = allowed_groups[group_by]

    total_filters = []
    total_parameters = []

    selected_filters = [
        f"LOWER({group_column}) = LOWER(%s)"
    ]

    selected_parameters = [value]

    if year is not None:

        total_filters.append(
            "year = %s"
        )

        total_parameters.append(
            year
        )

        selected_filters.append(
            "year = %s"
        )

        selected_parameters.append(
            year
        )

    total_where = ""

    if total_filters:
        total_where = (
            "WHERE "
            + " AND ".join(total_filters)
        )

    selected_where = (
        "WHERE "
        + " AND ".join(selected_filters)
    )

    query = f"""
        SELECT

            (
                SELECT COALESCE(
                    SUM({metric_column}),
                    0
                )
                FROM financials
                {selected_where}
            ) AS selected_value,

            (
                SELECT COALESCE(
                    SUM({metric_column}),
                    0
                )
                FROM financials
                {total_where}
            ) AS total_value
    """

    parameters = (
        selected_parameters
        + total_parameters
    )

    with get_database_connection() as connection:
        with connection.cursor(
            row_factory=dict_row
        ) as cursor:

            cursor.execute(
                query,
                parameters
            )

            row = cursor.fetchone()

    selected_value = (
        row["selected_value"]
        if row
        else 0
    )

    total_value = (
        row["total_value"]
        if row
        else 0
    )

    percentage = 0

    if total_value:
        percentage = (
            selected_value
            / total_value
        ) * 100

    return {
        "metric": metric,
        "group_by": group_by,
        "value": value,
        "year": year,
        "selected_value": selected_value,
        "total_value": total_value,
        "percentage": percentage,
    }

from datetime import date


def get_financial_statistics(
    metric: str,
    aggregation: str = "sum",
    group_by: str = "total",
    year: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    country: str | None = None,
    product: str | None = None,
    segment: str | None = None,
    order: str = "highest",
    limit: int = 20,
):
    allowed_metrics = {
        "sales": "sales",
        "profit": "profit",
        "cogs": "cogs",
        "gross_sales": "gross_sales",
        "discounts": "discounts",
        "units_sold": "units_sold",
        "sale_price": "sale_price",
        "manufacturing_price": "manufacturing_price",
    }

    allowed_aggregations = {
        "sum": "SUM",
        "average": "AVG",
        "minimum": "MIN",
        "maximum": "MAX",
    }

    allowed_groups = {
        "total": None,
        "country": "country",
        "product": "product",
        "segment": "segment",
        "year": "year",
        "month": "month_name",
        "discount_band": "discount_band",
    }

    if metric not in allowed_metrics:
        raise ValueError("Invalid financial metric.")

    if aggregation not in allowed_aggregations:
        raise ValueError("Invalid aggregation.")

    if group_by not in allowed_groups:
        raise ValueError("Invalid grouping.")

    if order not in {"highest", "lowest"}:
        raise ValueError("Invalid ordering option.")

    if from_date and to_date:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)

        if start > end:
            raise ValueError(
                "The start date cannot be after the end date."
            )

    limit = max(1, min(limit, 100))

    metric_column = allowed_metrics[metric]
    sql_aggregation = allowed_aggregations[aggregation]
    group_column = allowed_groups[group_by]

    filters = []
    parameters = []

    if year is not None:
        filters.append("year = %s")
        parameters.append(year)

    if from_date:
        filters.append("date >= %s")
        parameters.append(
            date.fromisoformat(from_date)
        )

    if to_date:
        filters.append("date <= %s")
        parameters.append(
            date.fromisoformat(to_date)
        )

    if country:
        filters.append(
            "LOWER(country) = LOWER(%s)"
        )
        parameters.append(country)

    if product:
        filters.append(
            "LOWER(product) = LOWER(%s)"
        )
        parameters.append(product)

    if segment:
        filters.append(
            "LOWER(segment) = LOWER(%s)"
        )
        parameters.append(segment)

    where_clause = ""

    if filters:
        where_clause = (
            "WHERE " + " AND ".join(filters)
        )

    if group_by == "total":

        query = f"""
            SELECT
                COALESCE(
                    {sql_aggregation}({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
        """

    elif group_by == "month":

        direction = (
            "DESC"
            if order == "highest"
            else "ASC"
        )

        query = f"""
            SELECT
                month_name AS group_name,
                month_number,
                COALESCE(
                    {sql_aggregation}({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
            GROUP BY
                month_name,
                month_number
            ORDER BY value {direction}
            LIMIT %s
        """

        parameters.append(limit)

    else:

        direction = (
            "DESC"
            if order == "highest"
            else "ASC"
        )

        query = f"""
            SELECT
                {group_column} AS group_name,
                COALESCE(
                    {sql_aggregation}({metric_column}),
                    0
                ) AS value
            FROM financials
            {where_clause}
            GROUP BY {group_column}
            ORDER BY value {direction}
            LIMIT %s
        """

        parameters.append(limit)

    with get_database_connection() as connection:

        with connection.cursor(
            row_factory=dict_row
        ) as cursor:

            cursor.execute(
                query,
                parameters,
            )

            rows = cursor.fetchall()

    return {
        "metric": metric,
        "aggregation": aggregation,
        "group_by": group_by,
        "order": order,
        "filters": {
            "year": year,
            "from_date": from_date,
            "to_date": to_date,
            "country": country,
            "product": product,
            "segment": segment,
        },
        "rows": rows,
    }
from datetime import date

from psycopg.rows import dict_row

from backend.database import get_database_connection


def get_order_summary(
    from_date: str,
    to_date: str,
    group_by: str = "total",
    provider: str | None = None
):

    # Step 1: Validate the dates

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

    # Step 2: Validate the grouping option

    allowed_groups = ["total", "provider", "date"]

    if group_by not in allowed_groups:
        raise ValueError(
            "Invalid grouping option."
        )

    # Step 3: Prepare the filter

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

    # Step 4: Select the correct SQL query

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

    # Step 5: Execute the query

    with get_database_connection() as connection:

        with connection.cursor(
            row_factory=dict_row
        ) as cursor:

            cursor.execute(
                query,
                parameters
            )

            rows = cursor.fetchall()

    # Step 6: Return structured results

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
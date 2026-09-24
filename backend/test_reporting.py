from backend.reporting import get_order_summary


def run_tests():

    print("\nTEST 1: TOTAL ORDERS")

    result = get_order_summary(
        from_date="2026-09-01",
        to_date="2026-09-03",
        group_by="total"
    )

    print(result)

    print("\nTEST 2: ORDERS BY PROVIDER")

    result = get_order_summary(
        from_date="2026-09-01",
        to_date="2026-09-03",
        group_by="provider"
    )

    print(result)

    print("\nTEST 3: ORDERS BY DATE")

    result = get_order_summary(
        from_date="2026-09-01",
        to_date="2026-09-03",
        group_by="date"
    )

    print(result)

    print("\nTEST 4: ALPHA ORDERS")

    result = get_order_summary(
        from_date="2026-09-01",
        to_date="2026-09-03",
        group_by="total",
        provider="Alpha"
    )

    print(result)


if __name__ == "__main__":
    run_tests()
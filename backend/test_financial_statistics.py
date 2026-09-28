from backend.reporting import (
    get_financial_statistics,
)


print("\nAVERAGE SALE PRICE")
print(
    get_financial_statistics(
        metric="sale_price",
        aggregation="average",
        group_by="total",
    )
)


print("\nAVERAGE PROFIT BY PRODUCT")
print(
    get_financial_statistics(
        metric="profit",
        aggregation="average",
        group_by="product",
    )
)


print("\nLOWEST SALES COUNTRY")
print(
    get_financial_statistics(
        metric="sales",
        aggregation="sum",
        group_by="country",
        order="lowest",
        limit=1,
    )
)


print("\n2014 CANADA AVERAGE PROFIT")
print(
    get_financial_statistics(
        metric="profit",
        aggregation="average",
        group_by="total",
        year=2014,
        country="Canada",
    )
)


print("\nDATE RANGE")
print(
    get_financial_statistics(
        metric="sales",
        aggregation="sum",
        group_by="month",
        from_date="2014-03-01",
        to_date="2014-06-30",
    )
)
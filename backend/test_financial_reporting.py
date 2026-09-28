from backend.reporting import get_financial_summary


print("\n1. TOTAL SALES")
print(
    get_financial_summary(
        metric="sales",
        group_by="total"
    )
)


print("\n2. SALES BY COUNTRY")
print(
    get_financial_summary(
        metric="sales",
        group_by="country"
    )
)


print("\n3. PROFIT BY PRODUCT")
print(
    get_financial_summary(
        metric="profit",
        group_by="product"
    )
)


print("\n4. SALES BY MONTH")
print(
    get_financial_summary(
        metric="sales",
        group_by="month"
    )
)


print("\n5. PROFIT FOR 2014")
print(
    get_financial_summary(
        metric="profit",
        group_by="total",
        year=2014
    )
)
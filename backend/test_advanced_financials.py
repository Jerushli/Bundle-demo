from backend.reporting import (
    get_financial_comparison,
    get_percentage_of_total,
)


print("\nCANADA VS GERMANY")
print(
    get_financial_comparison(
        metric="sales",
        group_by="country",
        values=[
            "Canada",
            "Germany",
        ],
    )
)


print("\nGOVERNMENT SALES %")
print(
    get_percentage_of_total(
        metric="sales",
        group_by="segment",
        value="Government",
    )
)


print("\nCANADA VS FRANCE 2014")
print(
    get_financial_comparison(
        metric="profit",
        group_by="country",
        values=[
            "Canada",
            "France",
        ],
        year=2014,
    )
)
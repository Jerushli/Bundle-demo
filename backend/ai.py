import os
import json
import re

from pathlib import Path
from decimal import Decimal

from dotenv import load_dotenv
from groq import Groq

from backend.reporting import (
    get_financial_summary,
    get_financial_comparison,
    get_percentage_of_total,
    get_financial_statistics,
)


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Root .env
load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing")

GROQ_API_KEY = GROQ_API_KEY.strip()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)


if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing from the .env file"
    )


client = Groq(
    api_key=GROQ_API_KEY,
    timeout=30.0,
)


# ============================================================
# TOOL 1 — FINANCIAL SUMMARY
# ============================================================

FINANCIAL_SUMMARY_TOOL = {
    "type": "function",

    "function": {

        "name": "get_financial_summary",

        "description": (
            "Retrieve aggregated financial information from "
            "PostgreSQL. Use this for totals, rankings, grouped "
            "results, top countries, top products, sales by "
            "segment, monthly results, yearly results, and similar "
            "single-dimension financial analysis."
        ),

        "parameters": {

            "type": "object",

            "properties": {

                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                    "description": (
                        "The financial metric to calculate."
                    ),
                },

                "group_by": {
                    "type": "string",
                    "enum": [
                        "total",
                        "country",
                        "product",
                        "segment",
                        "year",
                        "month",
                        "discount_band",
                    ],
                    "description": (
                        "How the result should be grouped."
                    ),
                },

                "year": {
                    "type": "integer",
                    "description": (
                        "Optional year filter such as 2014."
                    ),
                },

                "country": {
                    "type": "string",
                    "description": (
                        "Optional country filter."
                    ),
                },

                "product": {
                    "type": "string",
                    "description": (
                        "Optional product filter."
                    ),
                },

                "segment": {
                    "type": "string",
                    "description": (
                        "Optional segment filter."
                    ),
                },

                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum grouped rows to return. "
                        "Use small limits for top-N questions."
                    ),
                    "default": 20,
                },
            },

            "required": [
                "metric",
                "group_by",
            ],
        },
    },
}


# ============================================================
# TOOL 2 — FINANCIAL COMPARISON
# ============================================================

FINANCIAL_COMPARISON_TOOL = {
    "type": "function",

    "function": {

        "name": "get_financial_comparison",

        "description": (
            "Compare the same financial metric across explicitly "
            "named countries, products, segments, or discount bands. "
            "Use this when the user says compare, versus, vs, "
            "difference between, or asks about multiple named groups."
        ),

        "parameters": {

            "type": "object",

            "properties": {

                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                },

                "group_by": {
                    "type": "string",
                    "enum": [
                        "country",
                        "product",
                        "segment",
                        "discount_band",
                    ],
                },

                "values": {
                    "type": "array",

                    "items": {
                        "type": "string"
                    },

                    "minItems": 1,

                    "description": (
                        "Names that should be compared. "
                        "Example: ['Canada', 'Germany']."
                    ),
                },

                "year": {
                    "type": "integer",
                    "description": (
                        "Optional year filter."
                    ),
                },
            },

            "required": [
                "metric",
                "group_by",
                "values",
            ],
        },
    },
}


# ============================================================
# TOOL 3 — PERCENTAGE OF TOTAL
# ============================================================

PERCENTAGE_TOOL = {
    "type": "function",

    "function": {

        "name": "get_percentage_of_total",

        "description": (
            "Calculate how much one country, product, segment, "
            "or discount band contributes to the overall total "
            "for a financial metric. Use this for percentage, "
            "share, contribution, proportion, or percent-of-total "
            "questions."
        ),

        "parameters": {

            "type": "object",

            "properties": {

                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                },

                "group_by": {
                    "type": "string",
                    "enum": [
                        "country",
                        "product",
                        "segment",
                        "discount_band",
                    ],
                },

                "value": {
                    "type": "string",
                    "description": (
                        "The specific member whose contribution "
                        "should be calculated. Example: Government."
                    ),
                },

                "year": {
                    "type": "integer",
                    "description": (
                        "Optional year filter."
                    ),
                },
            },

            "required": [
                "metric",
                "group_by",
                "value",
            ],
        },
    },
}

FINANCIAL_STATISTICS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_financial_statistics",

        "description": (
            "Calculate sums, averages, minimums or maximums "
            "for financial metrics, optionally grouped and "
            "filtered by year, date range, country, product "
            "or segment."
        ),

        "parameters": {
            "type": "object",

            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                        "sale_price",
                        "manufacturing_price",
                    ],
                },

                "aggregation": {
                    "type": "string",
                    "enum": [
                        "sum",
                        "average",
                        "minimum",
                        "maximum",
                    ],
                },

                "group_by": {
                    "type": "string",
                    "enum": [
                        "total",
                        "country",
                        "product",
                        "segment",
                        "year",
                        "month",
                        "discount_band",
                    ],
                },

                "year": {
                    "type": "integer"
                },

                "from_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD"
                },

                "to_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD"
                },

                "country": {
                    "type": "string"
                },

                "product": {
                    "type": "string"
                },

                "segment": {
                    "type": "string"
                },

                "order": {
                    "type": "string",
                    "enum": [
                        "highest",
                        "lowest",
                    ],
                },

                "limit": {
                    "type": "integer"
                },
            },

            "required": [
                "metric",
                "aggregation",
                "group_by",
            ],
        },
    },
}

METRIC_COMPARISON_TOOL = {
    "type": "function",

    "function": {
        "name": "get_metric_comparison",

        "description": (
            "Compare two or more different financial metrics "
            "using the same filters. Use this when the user "
            "asks to compare sales with profit, gross sales "
            "with sales, COGS with profit, discounts with sales, "
            "or other different financial measures."
        ),

        "parameters": {
            "type": "object",

            "properties": {
                "metrics": {
                    "type": "array",

                    "items": {
                        "type": "string",

                        "enum": [
                            "sales",
                            "profit",
                            "cogs",
                            "gross_sales",
                            "discounts",
                        ],
                    },

                    "minItems": 2,
                    "maxItems": 5,
                },

                "year": {
                    "type": "integer"
                },

                "country": {
                    "type": "string"
                },

                "product": {
                    "type": "string"
                },

                "segment": {
                    "type": "string"
                },
            },

            "required": [
                "metrics"
            ],
        },
    },
}

GROWTH_ANALYSIS_TOOL = {
    "type": "function",

    "function": {
        "name": "get_growth_analysis",

        "description": (
            "Compare the same financial metric between two years "
            "and calculate absolute change and percentage growth. "
            "Use this for year-over-year growth, increase, decrease, "
            "change between years, or annual growth-rate questions."
        ),

        "parameters": {
            "type": "object",

            "properties": {

                "metric": {
                    "type": "string",

                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                },

                "start_year": {
                    "type": "integer"
                },

                "end_year": {
                    "type": "integer"
                },

                "country": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "product": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "segment": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
            },

            "required": [
                "metric",
                "start_year",
                "end_year",
            ],
        },
    },
}

MONTHLY_TREND_TOOL = {
    "type": "function",

    "function": {
        "name": "get_monthly_trend",

        "description": (
            "Analyze a financial metric month by month. "
            "Use this for monthly trends, month-over-month "
            "changes, highest or lowest month, biggest monthly "
            "increase or decrease, and upward/downward trend questions."
        ),

        "parameters": {
            "type": "object",

            "properties": {
                "metric": {
                    "type": "string",

                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                },

                "year": {
                    "type": ["integer", "null"]
                },

                "country": {
                    "type": ["string", "null"]
                },

                "product": {
                    "type": ["string", "null"]
                },

                "segment": {
                    "type": ["string", "null"]
                },
            },

            "required": [
                "metric"
            ],
        },
    },
}

MONTHLY_GROWTH_TOOL = {
    "type": "function",

    "function": {
        "name": "get_monthly_growth",

        "description": (
            "Calculate month-over-month financial growth. "
            "Use this for percentage change between two named months, "
            "strongest monthly growth, biggest monthly increase, "
            "biggest monthly decline, or month-over-month analysis. "
            "Do not invent from_month or to_month when the user "
            "does not explicitly name months."
        ),

        "parameters": {
            "type": "object",

            "properties": {

                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold",
                    ],
                },

                "year": {
                    "type": [
                        "integer",
                        "null"
                    ]
                },

                "from_month": {
                    "type": [
                        "string",
                        "null"
                    ],

                    "description": (
                        "Starting month only when the user "
                        "explicitly names a starting month. "
                        "Otherwise use null."
                    ),
                },

                "to_month": {
                    "type": [
                        "string",
                        "null"
                    ],

                    "description": (
                        "Ending month only when the user "
                        "explicitly names an ending month. "
                        "Otherwise use null."
                    ),
                },

                "country": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "product": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "segment": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
            },

            "required": [
                "metric"
            ],
        },
    },
}

FINANCIAL_KPI_TOOL = {
    "type": "function",

    "function": {
        "name": "get_financial_kpi",

        "description": (
            "Calculate business financial ratios and KPIs. "
            "Use this for profit margin, discount rate, "
            "COGS ratio, and average revenue per unit sold."
        ),

        "parameters": {
            "type": "object",

            "properties": {

                "kpi": {
                    "type": "string",

                    "enum": [
                        "profit_margin",
                        "discount_rate",
                        "cogs_ratio",
                        "revenue_per_unit",
                    ],
                },

                "year": {
                    "type": [
                        "integer",
                        "null"
                    ]
                },

                "country": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "product": {
                    "type": [
                        "string",
                        "null"
                    ]
                },

                "segment": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
            },

            "required": [
                "kpi"
            ],
        },
    },
}

RANKING_CONTRIBUTION_TOOL = {
    "type": "function",
    "function": {
        "name": "get_ranking_contribution",
        "description": (
            "Rank countries, products, or segments by a financial "
            "metric and calculate each one's percentage contribution "
            "to the total. Use for top N contributors, largest shares, "
            "ranking with percentages, and contribution breakdowns."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "sales",
                        "profit",
                        "cogs",
                        "gross_sales",
                        "discounts",
                        "units_sold"
                    ]
                },
                "group_by": {
                    "type": "string",
                    "enum": [
                        "country",
                        "product",
                        "segment"
                    ]
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20
                },
                "year": {
                    "type": ["integer", "null"]
                },
                "country": {
                    "type": ["string", "null"]
                },
                "product": {
                    "type": ["string", "null"]
                },
                "segment": {
                    "type": ["string", "null"]
                }
            },
            "required": [
                "metric",
                "group_by"
            ]
        }
    }
}

TOOLS = [
    FINANCIAL_SUMMARY_TOOL,
    FINANCIAL_COMPARISON_TOOL,
    PERCENTAGE_TOOL,
    FINANCIAL_STATISTICS_TOOL,
    METRIC_COMPARISON_TOOL,
    GROWTH_ANALYSIS_TOOL,
    MONTHLY_TREND_TOOL,
    MONTHLY_GROWTH_TOOL,
    FINANCIAL_KPI_TOOL,
    RANKING_CONTRIBUTION_TOOL,
]


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Bundle Data Assistant.

You analyze financial data stored in PostgreSQL.

The financial dataset contains:

- segment
- country
- product
- discount band
- units sold
- manufacturing price
- sale price
- gross sales
- discounts
- sales
- COGS
- profit
- date
- month
- year


AVAILABLE TOOLS


1. get_financial_summary

Use this for:

- totals
- rankings
- highest / lowest
- top products
- top countries
- grouped results
- sales by segment
- profit by product
- monthly results
- yearly results
- filtered results


Examples:

"Which country generated the highest sales?"

metric = sales
group_by = country
limit = 1


"Which product made the most profit?"

metric = profit
group_by = product


"What was total profit in 2014?"

metric = profit
group_by = total
year = 2014


"Which product made the most profit in 2014?"

metric = profit
group_by = product
year = 2014


"Show the top 3 products by sales"

metric = sales
group_by = product
limit = 3


"Show sales by segment"

metric = sales
group_by = segment
limit = 20



2. get_financial_comparison

Use this when the user explicitly compares named values.

Examples:

"Compare sales of Canada and Germany"

metric = sales
group_by = country
values = ["Canada", "Germany"]


"Compare Canada and France profit in 2014"

metric = profit
group_by = country
values = ["Canada", "France"]
year = 2014


"Compare Paseo and VTT sales"

metric = sales
group_by = product
values = ["Paseo", "VTT"]



3. get_percentage_of_total

Use this for:

- percentage of total
- share of total
- contribution
- proportion


Examples:

"What percentage of total sales came from Government?"

metric = sales
group_by = segment
value = Government


"What percentage of 2014 profit came from Canada?"

metric = profit
group_by = country
value = Canada
year = 2014

4. get_financial_statistics

Use this tool when the question asks for:

- average
- mean
- minimum
- maximum
- lowest
- date ranges
- average price
- average profit
- average units sold

Examples:

"What is the average sale price?"

metric = sale_price
aggregation = average
group_by = total


"Which product has the highest average profit?"

metric = profit
aggregation = average
group_by = product
order = highest


"Which country had the lowest sales?"

metric = sales
aggregation = sum
group_by = country
order = lowest
limit = 1


"What was average profit in Canada in 2014?"

metric = profit
aggregation = average
group_by = total
country = Canada
year = 2014

5. get_metric_comparison

Use this when DIFFERENT METRICS are being compared.

Examples:

"Compare sales and profit"

metrics = ["sales", "profit"]


"Compare gross sales and sales"

metrics = ["gross_sales", "sales"]


"Compare revenue and profit"

Interpret revenue as gross_sales.

metrics = ["gross_sales", "profit"]


"Compare sales and profit in 2014"

metrics = ["sales", "profit"]
year = 2014


IMPORTANT:

get_financial_comparison compares MEMBERS of one dimension:

Canada vs Germany
Paseo vs VTT

get_metric_comparison compares DIFFERENT METRICS:

sales vs profit
gross sales vs sales
COGS vs profit

Never use get_financial_comparison to compare two different metrics.

6. get_growth_analysis

Use this when the user asks about:

- growth
- increase
- decrease
- change between years
- year-over-year change
- percentage growth
- how a metric changed from one year to another

Examples:

"How did sales change from 2013 to 2014?"

metric = sales
start_year = 2013
end_year = 2014


"What was profit growth from 2013 to 2014?"

metric = profit
start_year = 2013
end_year = 2014


"How did sales in Canada change from 2013 to 2014?"

metric = sales
country = Canada
start_year = 2013
end_year = 2014

7. get_monthly_trend

Use this tool for month-by-month analysis.

Examples:

"Show the monthly sales trend in 2014"

metric = sales
year = 2014


"Show monthly profit"

metric = profit


"Which month had the highest sales in 2014?"

metric = sales
year = 2014


"Which month had the biggest sales increase in 2014?"

metric = sales
year = 2014


"Was profit trending upward or downward in 2014?"

metric = profit
year = 2014


"Show monthly sales trend for Canada in 2014"

metric = sales
country = Canada
year = 2014

IMPORTANT TREND RULE:

Questions asking whether a metric was:

- trending upward
- trending downward
- increasing over time
- decreasing over time
- showing an upward trend
- showing a downward trend

must use get_monthly_trend.

Do not use get_financial_statistics for trend-direction questions.

Example:

"Was profit trending upward or downward in 2014?"

Use:

get_monthly_trend

metric = profit
year = 2014

8. get_monthly_growth

Use this for month-over-month percentage changes.

Examples:

"What was sales growth from March to April 2014?"

metric = sales
year = 2014
from_month = March
to_month = April


"Which month had the strongest sales growth in 2014?"

metric = sales
year = 2014


"Which month had the biggest profit decline in 2014?"

metric = profit
year = 2014


IMPORTANT:

Use get_monthly_trend for general trend direction.

Use get_monthly_growth when the question asks for:
- percentage change
- growth rate
- strongest growth
- biggest increase
- biggest decline
- month-over-month change

GROWTH TOOL ROUTING RULES

There are two different growth tools.

Use get_growth_analysis ONLY when comparing YEARS.

Examples:

"Sales growth from 2013 to 2014"
"How did profit change between 2013 and 2014?"

These use:
get_growth_analysis


Use get_monthly_growth whenever MONTH NAMES are mentioned.

Examples:

"Sales growth from March to April 2014"
"Profit change from June to July"
"Month-over-month sales growth"
"Which month had the strongest growth?"
"Which month had the biggest decline?"

These use:
get_monthly_growth


IMPORTANT:

If the question contains month names such as:

January
February
March
April
May
June
July
August
September
October
November
December

NEVER use get_growth_analysis.

Use get_monthly_growth.

MONTH ARGUMENT RULE:

Only provide from_month and to_month when the user explicitly
names two months.

Example:

"What was sales growth from March to April 2014?"

from_month = March
to_month = April


But for:

"Which month had the strongest sales growth in 2014?"

from_month = null
to_month = null


And for:

"Which month had the biggest profit decline in 2014?"

from_month = null
to_month = null


Never invent months that the user did not mention.

9. get_financial_kpi

Use this for financial ratios and business KPIs.

Examples:

"What was the profit margin in 2014?"

kpi = profit_margin
year = 2014


"What was Canada's profit margin in 2014?"

kpi = profit_margin
country = Canada
year = 2014


"What percentage of gross sales was discounted?"

kpi = discount_rate


"What was the COGS ratio in 2014?"

kpi = cogs_ratio
year = 2014


"What was the average revenue per unit sold?"

kpi = revenue_per_unit


FORMULAS

profit_margin =
profit / sales * 100

discount_rate =
discounts / gross_sales * 100

cogs_ratio =
cogs / sales * 100

revenue_per_unit =
sales / units_sold

Use get_financial_kpi for these questions.
Do not use get_percentage_of_total for these KPI ratios.

10. get_ranking_contribution

Use this tool when a user asks for ranked groups
AND their contribution percentages.

Examples:

"Show top 5 products by sales and their shares"

metric = sales
group_by = product
limit = 5

"Which 3 countries contributed most to profit in 2014?"

metric = profit
group_by = country
limit = 3
year = 2014

"Show the top 5 segments by sales contribution"

metric = sales
group_by = segment
limit = 5

Use get_ranking_contribution for combined ranking
and contribution questions.

Use get_percentage_of_total when the user asks
for one specific group's share.

IMPORTANT RULES

Never invent database values.

Always call a tool when answering a question that requires
financial database information.

Do not write or execute arbitrary SQL.

Only use the approved reporting tools.

Use get_financial_comparison when multiple specific groups
are explicitly being compared.

Use get_percentage_of_total for percentage/share/contribution
questions.

Use get_financial_summary for ordinary totals, rankings,
filters, top-N and grouped analyses.

GROUPED RESULT RULES

If the user asks to "show", "list", "display", or asks for a metric
"by country", "by product", "by segment", "by month", "by year",
or "by discount band" without asking for top, highest, lowest,
most, best, or a specific number of results:

return the full grouped result.

Do NOT set limit = 1 for ordinary grouped questions.

Examples:

"Show sales by country"
metric = sales
group_by = country
limit = 20

"Show profit by product"
metric = profit
group_by = product
limit = 20

"Show sales by month"
metric = sales
group_by = month
limit = 20

Only use limit = 1 when the user explicitly asks for a single
highest/lowest/top/most/best result.

Example:

"Which country generated the highest sales?"
metric = sales
group_by = country
limit = 1

For questions such as highest, largest, most, top or best-selling,
the grouped result is ordered from highest to lowest.

If the question is unrelated to this financial dataset,
briefly explain what financial information you can analyze.

Keep answers concise and data-driven.

CONVERSATION CONTEXT RULES

The user may ask short follow-up questions.
Always use the recent conversation history to resolve them.

Preserve the analytical structure of the previous question unless
the user explicitly changes it.

Example 1:

User:
"Which country generated the highest sales?"

Assistant:
"Canada generated the highest sales."

User:
"What about profit?"

Interpret this as:

"Which country generated the highest profit?"

Use:
metric = profit
group_by = country
order = highest


Example 2:

User:
"Which product generated the highest sales?"

User:
"What about profit?"

Interpret this as:

"Which product generated the highest profit?"

Keep:
group_by = product

Change only:
metric = profit


Example 3:

User:
"Which country generated the highest sales?"

Assistant:
"Canada generated the highest sales."

User:
"Compare it with Germany."

Interpret "it" as Canada.

Use:
get_financial_comparison

metric = sales
group_by = country
values = ["Canada", "Germany"]


Example 4:

User:
"Which country generated the highest sales?"

Assistant:
"Canada generated the highest sales."

User:
"What about profit?"

Assistant:
"Canada generated ... profit."

User:
"Compare it with Germany."

Interpret this as comparing Canada and Germany using profit.

Use:
metric = profit
group_by = country
values = ["Canada", "Germany"]


FOLLOW-UP RULES

If the user says:
- "what about profit?"
- "what about sales?"
- "what about units sold?"

change only the metric and preserve the previous grouping and filters.

If the user says:
- "compare it with X"
- "what about X?"
- "and X?"

resolve "it" using the most recent clearly identified
country, product, or segment.

Do not change a grouped analysis into a total analysis unless
the user explicitly asks for a total.

Do not ask for clarification when the recent history clearly
identifies the subject.

Only ask for clarification when there is genuinely no clear
referent in the recent conversation.

"""


# ============================================================
# NUMBER FORMATTING
# ============================================================

def number_to_float(value):

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    return 0.0


def format_number(value):

    if value is None:
        return "0"

    if isinstance(value, Decimal):
        value = float(value)

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):

        if value.is_integer():
            return f"{int(value):,}"

        return f"{value:,.2f}"

    return str(value)


# ============================================================
# SUMMARY ANSWER FORMATTER
# ============================================================

def format_summary_answer(result):

    rows = result["rows"]

    metric = result["metric"]

    group_by = result["group_by"]

    filters = result["filters"]

    readable_metric = metric.replace(
        "_",
        " ",
    )

    if not rows:
        return (
            "No matching financial records were found."
        )

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    if group_by == "total":

        value = rows[0]["value"]

        filter_parts = []

        if filters.get("year"):
            filter_parts.append(
                f"in {filters['year']}"
            )

        if filters.get("country"):
            filter_parts.append(
                f"for {filters['country']}"
            )

        if filters.get("product"):
            filter_parts.append(
                f"for product {filters['product']}"
            )

        if filters.get("segment"):
            filter_parts.append(
                f"for segment {filters['segment']}"
            )

        filter_text = ""

        if filter_parts:
            filter_text = (
                " " + " ".join(filter_parts)
            )

        return (
            f"Total {readable_metric}{filter_text} "
            f"is {format_number(value)}."
        )

    # --------------------------------------------------------
    # GROUPED
    # --------------------------------------------------------

    first = rows[0]

    group_name = first.get(
        "group_name"
    )

    value = first.get(
        "value"
    )

    if group_by == "month":

        return (
            f"Monthly {readable_metric} results "
            f"returned {len(rows)} month(s)."
        )

    return (
        f"The highest {readable_metric} by "
        f"{group_by.replace('_', ' ')} is "
        f"{group_name} with "
        f"{format_number(value)}. "
        f"{len(rows)} result(s) were returned."
    )


# ============================================================
# COMPARISON ANSWER FORMATTER
# ============================================================

def format_comparison_answer(result):

    rows = result["rows"]

    metric = result["metric"]

    year = result.get("year")

    readable_metric = metric.replace(
        "_",
        " ",
    )

    if not rows:

        return (
            "No matching records were found "
            "for the requested comparison."
        )

    if len(rows) == 1:

        row = rows[0]

        return (
            f"{row['group_name']} has "
            f"{format_number(row['value'])} "
            f"{readable_metric}"
            + (
                f" in {year}."
                if year
                else "."
            )
        )

    first = rows[0]
    second = rows[1]

    first_value = number_to_float(
        first["value"]
    )

    second_value = number_to_float(
        second["value"]
    )

    difference = abs(
        first_value - second_value
    )

    year_text = (
        f" in {year}"
        if year
        else ""
    )

    return (
        f"{first['group_name']} has "
        f"{format_number(first['value'])} "
        f"{readable_metric}{year_text}, while "
        f"{second['group_name']} has "
        f"{format_number(second['value'])}. "
        f"The difference is "
        f"{format_number(difference)}."
    )


# ============================================================
# PERCENTAGE ANSWER FORMATTER
# ============================================================

def format_percentage_answer(result):

    percentage = number_to_float(
        result["percentage"]
    )

    metric = result["metric"]

    group_by = result["group_by"]

    value = result["value"]

    selected_value = result[
        "selected_value"
    ]

    total_value = result[
        "total_value"
    ]

    year = result.get("year")

    readable_metric = metric.replace(
        "_",
        " ",
    )

    year_text = (
        f" in {year}"
        if year
        else ""
    )

    return (
        f"{value} contributed "
        f"{percentage:.2f}% of total "
        f"{readable_metric}{year_text}. "
        f"Its {readable_metric} was "
        f"{format_number(selected_value)} "
        f"out of {format_number(total_value)}."
    )


# ============================================================
# MAIN CHAT FUNCTION
# ============================================================

def process_chat(
    question: str,
    history: list[dict] | None = None,
    context: dict | None = None,
):

    normalized_question = question.strip().lower()

    # ========================================================
    # DETERMINISTIC FOLLOW-UP HANDLING
    # ========================================================

    if context:
        previous_metric = context.get("metric")
        previous_group = context.get("group_by")
        previous_entity = context.get("entity")

        metric_followups = {
            "what about profit?": "profit",
            "what about profit": "profit",
            "what about sales?": "sales",
            "what about sales": "sales",
            "what about units sold?": "units_sold",
            "what about units sold": "units_sold",
            "what about cogs?": "cogs",
            "what about cogs": "cogs",
            "what about discounts?": "discounts",
            "what about discounts": "discounts",
        }

        if (
            normalized_question in metric_followups
            and previous_group
        ):
            new_metric = metric_followups[
                normalized_question
            ]

            result = get_financial_summary(
                metric=new_metric,
                group_by=previous_group,
                limit=1,
            )

            return {
                "answer": format_summary_answer(result),
                "rows": result["rows"],
                "group_by": result["group_by"],
                "metric": result["metric"],
                "source": "financials",
            }

        compare_prefix = "compare it with "

        if (
            normalized_question.startswith(compare_prefix)
            and previous_entity
            and previous_metric
            and previous_group
        ):
            other_entity = (
                question.strip()[len(compare_prefix):]
                .rstrip(".?!")
                .strip()
            )

            if other_entity:
                result = get_financial_comparison(
                    metric=previous_metric,
                    group_by=previous_group,
                    values=[
                        previous_entity,
                        other_entity,
                    ],
                )

                return {
                    "answer": format_comparison_answer(
                        result
                    ),
                    "rows": result["rows"],
                    "group_by": result["group_by"],
                    "metric": result["metric"],
                    "source": "financials",
                }

    # ========================================================
    # BUILD CONTEXT BEFORE GROQ CALL
    # ========================================================

    context_text = ""

    if context:
        context_text = f"""

MOST RECENT ANALYSIS CONTEXT

metric: {context.get("metric")}
group_by: {context.get("group_by")}
entity: {context.get("entity")}

Use this context for follow-up questions.

If the user changes only the metric, preserve the
previous grouping.

If the user says "compare it with X", interpret "it"
as the most recent entity.

Do not discard the previous analytical context unless
the user explicitly changes it.
"""

    messages = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + context_text
            ),
        }
    ]

    if history:
        for item in history[-8:]:

            role = item.get("role")
            content = item.get("content")

            if (
                role in {
                    "user",
                    "assistant",
                }
                and content
            ):
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # ========================================================
    # DETERMINISTIC TOOL ROUTING
    # ========================================================

    question_lower = question.lower()

    month_names = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

    monthly_growth_words = (
    "growth",
    "increase",
    "decrease",
    "decline",
    "change",
    "month-over-month",
    "month over month",
    "strongest",
    "biggest",
)

    mentions_month_name = any(
    month in question_lower
    for month in month_names
)

    asks_about_month = (
    "which month" in question_lower
    or "what month" in question_lower
)

    asks_growth = any(
    word in question_lower
    for word in monthly_growth_words
)

    if (
    (
        mentions_month_name
        and asks_growth
    )
    or
    (
        asks_about_month
        and asks_growth
    )
):
        selected_tool_choice = {
        "type": "function",
        "function": {
            "name": "get_monthly_growth"
        },
    }

    else:
        selected_tool_choice = "auto"

    
    response = (
        client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice=selected_tool_choice,
            temperature=0,
        )
    )

    assistant_message = (
        response.choices[0].message
    )

    # ========================================================
    # NO TOOL CALL
    # ========================================================

    if not assistant_message.tool_calls:
        return {
            "answer": (
                assistant_message.content
                or (
                    "I can help analyze sales, profit, "
                    "products, countries, segments and "
                    "other financial data."
                )
            ),
            "rows": [],
        }

    # ========================================================
    # EXECUTE TOOL
    # ========================================================

    tool_call = assistant_message.tool_calls[0]

    function_name = (
        tool_call.function.name
    )

    arguments = json.loads(
        tool_call.function.arguments
    )

    # --------------------------------------------------------
    # FINANCIAL SUMMARY
    # --------------------------------------------------------

    if function_name == "get_financial_summary":

        result = get_financial_summary(
            metric=arguments.get(
                "metric",
                "sales",
            ),
            group_by=arguments.get(
                "group_by",
                "total",
            ),
            year=arguments.get("year"),
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            limit=arguments.get(
                "limit",
                20,
            ),
        )

        return {
            "answer": format_summary_answer(
                result
            ),
            "rows": result["rows"],
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
            "tool_name": function_name,

            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    if function_name == "get_financial_comparison":

        result = get_financial_comparison(
            metric=arguments["metric"],
            group_by=arguments["group_by"],
            values=arguments["values"],
            year=arguments.get("year"),
        )

        return {
            "answer": format_comparison_answer(
                result
            ),
            "rows": result["rows"],
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
            "tool_name": function_name,

            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # PERCENTAGE OF TOTAL
    # --------------------------------------------------------

    if function_name == "get_percentage_of_total":

        result = get_percentage_of_total(
            metric=arguments["metric"],
            group_by=arguments["group_by"],
            value=arguments["value"],
            year=arguments.get("year"),
        )

        rows = [
            {
                "group_name": result["value"],
                "selected_value": result[
                    "selected_value"
                ],
                "total_value": result[
                    "total_value"
                ],
                "percentage": round(
                    number_to_float(
                        result["percentage"]
                    ),
                    2,
                ),
            }
        ]

        return {
            "answer": format_percentage_answer(
                result
            ),
            "rows": rows,
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
            "tool_name": function_name,

            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # FINANCIAL STATISTICS
    # --------------------------------------------------------

    if function_name == "get_financial_statistics":

        result = get_financial_statistics(
            metric=arguments["metric"],
            aggregation=arguments[
                "aggregation"
            ],
            group_by=arguments["group_by"],
            year=arguments.get("year"),
            from_date=arguments.get(
                "from_date"
            ),
            to_date=arguments.get(
                "to_date"
            ),
            country=arguments.get(
                "country"
            ),
            product=arguments.get(
                "product"
            ),
            segment=arguments.get(
                "segment"
            ),
            order=arguments.get(
                "order",
                "highest",
            ),
            limit=arguments.get(
                "limit",
                20,
            ),
        )

        rows = result["rows"]

        readable_metric = (
            result["metric"]
            .replace("_", " ")
        )

        readable_aggregation = (
            result["aggregation"]
        )

        if not rows:
            answer = (
                "No matching financial records were found."
            )

        elif result["group_by"] == "total":
            answer = (
                f"The {readable_aggregation} "
                f"{readable_metric} is "
                f"{format_number(rows[0]['value'])}."
            )

        else:
            first = rows[0]

            answer = (
                f"The {result['order']} "
                f"{readable_aggregation} "
                f"{readable_metric} by "
                f"{result['group_by']} is "
                f"{first['group_name']} with "
                f"{format_number(first['value'])}."
            )

        return {
            "answer": answer,
            "rows": rows,
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
            "tool_name": function_name,

            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # METRIC COMPARISON
    # --------------------------------------------------------

    if function_name == "get_metric_comparison":

        metrics = arguments["metrics"]

        rows = []

        for metric_name in metrics:

            metric_result = get_financial_summary(
                metric=metric_name,
                group_by="total",
                year=arguments.get("year"),
                country=arguments.get("country"),
                product=arguments.get("product"),
                segment=arguments.get("segment"),
                limit=1,
            )

            metric_rows = metric_result["rows"]

            if not metric_rows:
                continue

            rows.append({
                "group_name": (
                    metric_name
                    .replace("_", " ")
                    .title()
                ),
                "value": metric_rows[0]["value"],
            })

        if not rows:
            answer = (
                "No matching financial records "
                "were found for this comparison."
            )
        elif len(rows) == 1:
            answer = (
                f"{rows[0]['group_name']} is "
                f"{format_number(rows[0]['value'])}."
            )
        else:
            first = rows[0]
            second = rows[1]

            difference = abs(
                number_to_float(first["value"])
                -
                number_to_float(second["value"])
            )

            answer = (
                f"{first['group_name']} is "
                f"{format_number(first['value'])}, while "
                f"{second['group_name']} is "
                f"{format_number(second['value'])}. "
                f"The difference is "
                f"{format_number(difference)}."
            )

        # Add profit margin when comparing sales and profit.
        normalized_metrics = set(metrics)

        if (
            "sales" in normalized_metrics
            and "profit" in normalized_metrics
        ):
            sales_row = next(
                (
                    row
                    for row in rows
                    if row["group_name"] == "Sales"
                ),
                None,
            )
            profit_row = next(
                (
                    row
                    for row in rows
                    if row["group_name"] == "Profit"
                ),
                None,
            )

            if (
                sales_row
                and profit_row
                and number_to_float(sales_row["value"]) != 0
            ):
                margin = (
                    number_to_float(profit_row["value"])
                    / number_to_float(sales_row["value"])
                    * 100
                )

                answer += (
                    f" Profit margin is "
                    f"{margin:.2f}%."
                )

        return {
            "answer": answer,
            "rows": rows,
            "group_by": "metric",
            "metric": "metric_comparison",
            "source": "financials",
            "tool_name": function_name,
            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # GROWTH ANALYSIS
    # --------------------------------------------------------

    if function_name == "get_growth_analysis":

        metric = arguments["metric"]
        start_year = arguments["start_year"]
        end_year = arguments["end_year"]

        start_result = get_financial_summary(
            metric=metric,
            group_by="total",
            year=start_year,
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            limit=1,
        )

        end_result = get_financial_summary(
            metric=metric,
            group_by="total",
            year=end_year,
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            limit=1,
        )

        if not start_result["rows"] or not end_result["rows"]:
            return {
                "answer": (
                    "There is not enough matching data "
                    "to calculate growth."
                ),
                "rows": [],
                "group_by": "year",
                "metric": metric,
                "source": "financials",
                "tool_name": function_name,
            }

        start_value = number_to_float(start_result["rows"][0]["value"])
        end_value = number_to_float(end_result["rows"][0]["value"])
        change = end_value - start_value

        if start_value != 0:
            growth_percent = (change / abs(start_value)) * 100
        else:
            growth_percent = None

        rows = [
            {
                "group_name": str(start_year),
                "value": start_value,
            },
            {
                "group_name": str(end_year),
                "value": end_value,
            },
        ]

        readable_metric = metric.replace("_", " ")

        direction = (
            "increased"
            if change > 0
            else "decreased"
            if change < 0
            else "did not change"
        )

        if growth_percent is None:
            answer = (
                f"{readable_metric.title()} "
                f"{direction} from "
                f"{format_number(start_value)} in "
                f"{start_year} to "
                f"{format_number(end_value)} in "
                f"{end_year}. "
                f"The absolute change was "
                f"{format_number(abs(change))}."
            )
        else:
            answer = (
                f"{readable_metric.title()} "
                f"{direction} from "
                f"{format_number(start_value)} in "
                f"{start_year} to "
                f"{format_number(end_value)} in "
                f"{end_year}. "
                f"The change was "
                f"{format_number(abs(change))}, "
                f"or {abs(growth_percent):.2f}%."
            )

        return {
            "answer": answer,
            "rows": rows,
            "group_by": "year",
            "metric": metric,
            "source": "financials",
            "tool_name": function_name,
            "year": end_year,
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
            "start_year": start_year,
            "end_year": end_year,
            "change": change,
            "growth_percent": growth_percent,
        }


    # --------------------------------------------------------
    # MONTHLY GROWTH
    # --------------------------------------------------------

    if function_name == "get_monthly_growth":

        question_lower = question.lower()

        MONTHS = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        metric = arguments.get("metric")

        if not metric:
            if "profit" in question_lower:
                metric = "profit"
            elif "cogs" in question_lower:
                metric = "cogs"
            elif "gross sales" in question_lower:
                metric = "gross_sales"
            elif "discount" in question_lower:
                metric = "discounts"
            elif "units sold" in question_lower:
                metric = "units_sold"
            else:
                metric = "sales"

        year = arguments.get("year")

        if year is None:
            year_match = re.search(r"\b(19|20)\d{2}\b", question)
            if year_match:
                year = int(year_match.group(0))

        requested_from = arguments.get("from_month")
        requested_to = arguments.get("to_month")

        found_months = []

        for month_name in MONTHS:
            match = re.search(rf"\b{month_name}\b", question_lower)
            if match:
                found_months.append((match.start(), month_name))

        found_months.sort(key=lambda item: item[0])
        mentioned_months = [month for _, month in found_months]

        if not requested_from and len(mentioned_months) >= 1:
            requested_from = mentioned_months[0]

        if not requested_to and len(mentioned_months) >= 2:
            requested_to = mentioned_months[1]

        if requested_from:
            requested_from = str(requested_from).strip().lower()

        if requested_to:
            requested_to = str(requested_to).strip().lower()

        result = get_financial_summary(
            metric=metric,
            group_by="month",
            year=year,
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            limit=20,
        )

        source_rows = result.get("rows", [])

        if len(source_rows) < 2:
            return {
                "answer": "There is not enough monthly data to calculate month-over-month growth.",
                "rows": [],
                "group_by": "month_growth",
                "metric": "growth_percent",
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": arguments.get("country"),
                "product": arguments.get("product"),
                "segment": arguments.get("segment"),
            }

        monthly_rows = []

        for row in source_rows:
            raw_month = row.get("group_name") or row.get("month_name") or row.get("month")
            if raw_month is None:
                continue

            month_text = str(raw_month).strip().lower()
            month_number = None
            month_display = None

            if month_text in MONTHS:
                month_number = MONTHS[month_text]
                month_display = month_text.title()
            else:
                for name, number in MONTHS.items():
                    if month_text == name[:3]:
                        month_number = number
                        month_display = name.title()
                        break

            if month_number is None:
                try:
                    possible_number = int(month_text)
                    if 1 <= possible_number <= 12:
                        month_number = possible_number
                        month_display = next(
                            name.title()
                            for name, number in MONTHS.items()
                            if number == possible_number
                        )
                except ValueError:
                    pass

            if month_number is None:
                continue

            monthly_rows.append({
                "month_number": month_number,
                "month": month_display,
                "value": number_to_float(row.get("value")),
            })

        monthly_rows.sort(key=lambda row: row["month_number"])

        if len(monthly_rows) < 2:
            return {
                "answer": "The monthly records could not be ordered correctly.",
                "rows": [],
                "group_by": "month_growth",
                "metric": "growth_percent",
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": arguments.get("country"),
                "product": arguments.get("product"),
                "segment": arguments.get("segment"),
            }

        if requested_from and requested_to:
            from_row = next(
                (row for row in monthly_rows if row["month"].lower() == requested_from),
                None,
            )
            to_row = next(
                (row for row in monthly_rows if row["month"].lower() == requested_to),
                None,
            )

            if from_row is None or to_row is None:
                return {
                    "answer": "I could not find both requested months in the financial data.",
                    "rows": [],
                    "group_by": "month",
                    "metric": metric,
                    "source": "financials",
                    "tool_name": function_name,
                    "year": year,
                    "country": arguments.get("country"),
                    "product": arguments.get("product"),
                    "segment": arguments.get("segment"),
                }

            start_value = from_row["value"]
            end_value = to_row["value"]
            change = end_value - start_value
            growth_percent = (change / abs(start_value)) * 100 if start_value != 0 else None

            if change > 0:
                direction = "increased"
            elif change < 0:
                direction = "decreased"
            else:
                direction = "did not change"

            readable_metric = metric.replace("_", " ").title()
            answer = (
                f"{readable_metric} {direction} from {format_number(start_value)} in {from_row['month']} "
                f"to {format_number(end_value)} in {to_row['month']}."
            )
            if growth_percent is not None:
                answer += f" The percentage change was {abs(growth_percent):.2f}%."

            return {
                "answer": answer,
                "rows": [
                    {"group_name": from_row["month"], "value": start_value},
                    {"group_name": to_row["month"], "value": end_value},
                ],
                "group_by": "month",
                "metric": metric,
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": arguments.get("country"),
                "product": arguments.get("product"),
                "segment": arguments.get("segment"),
                "growth_percent": growth_percent,
                "change": change,
            }

        growth_rows = []

        for index in range(1, len(monthly_rows)):
            previous = monthly_rows[index - 1]
            current = monthly_rows[index]
            change = current["value"] - previous["value"]
            if previous["value"] != 0:
                percentage = (change / abs(previous["value"])) * 100
            else:
                percentage = None

            growth_rows.append({
                "group_name": current["month"],
                "value": round(percentage, 2) if percentage is not None else 0,
                "from_month": previous["month"],
                "to_month": current["month"],
                "previous_value": previous["value"],
                "current_value": current["value"],
                "change": change,
                "growth_percent": round(percentage, 2) if percentage is not None else None,
            })

        valid_rows = [row for row in growth_rows if row["growth_percent"] is not None]

        if not valid_rows:
            return {
                "answer": "Percentage growth could not be calculated because the previous monthly values were zero.",
                "rows": growth_rows,
                "group_by": "month_growth",
                "metric": "growth_percent",
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": arguments.get("country"),
                "product": arguments.get("product"),
                "segment": arguments.get("segment"),
            }

        strongest_growth = max(valid_rows, key=lambda row: row["growth_percent"])
        biggest_decline = min(valid_rows, key=lambda row: row["growth_percent"])
        readable_metric = metric.replace("_", " ").title()

        decline_words = ("decline", "decrease", "drop", "fell", "fall", "worst")
        asks_decline = any(word in question_lower for word in decline_words)
        growth_words = ("strongest", "highest growth", "biggest increase", "most growth")
        asks_growth = any(phrase in question_lower for phrase in growth_words)

        if asks_decline:
            decline_value = biggest_decline["growth_percent"]
            if decline_value < 0:
                answer = (
                    f"The biggest month-over-month {readable_metric} decline was from "
                    f"{biggest_decline['from_month']} to {biggest_decline['to_month']}, falling by {abs(decline_value):.2f}%."
                )
            else:
                answer = f"{readable_metric} did not have a negative month-over-month decline in the selected period."
        elif asks_growth:
            answer = (
                f"The strongest month-over-month {readable_metric} growth was from "
                f"{strongest_growth['from_month']} to {strongest_growth['to_month']} at {strongest_growth['growth_percent']:.2f}%."
            )
        else:
            answer = (
                f"The strongest month-over-month {readable_metric} growth was from "
                f"{strongest_growth['from_month']} to {strongest_growth['to_month']} at {strongest_growth['growth_percent']:.2f}%. "
                f"The biggest decline was from {biggest_decline['from_month']} to {biggest_decline['to_month']} at {biggest_decline['growth_percent']:.2f}%."
            )

        return {
            "answer": answer,
            "rows": growth_rows,
            "group_by": "month_growth",
            "metric": "growth_percent",
            "source": "financials",
            "tool_name": function_name,
            "year": year,
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

    # --------------------------------------------------------
    # FINANCIAL KPI
    # --------------------------------------------------------

    if function_name == "get_financial_kpi":

        kpi = arguments["kpi"]
        year = arguments.get("year")
        country = arguments.get("country")
        product = arguments.get("product")
        segment = arguments.get("segment")

        def get_total(metric_name):
            result = get_financial_summary(
                metric=metric_name,
                group_by="total",
                year=year,
                country=country,
                product=product,
                segment=segment,
                limit=1,
            )
            rows = result.get("rows", [])
            if not rows:
                return None
            return number_to_float(rows[0].get("value"))

        if kpi == "profit_margin":
            numerator = get_total("profit")
            denominator = get_total("sales")
            label = "Profit Margin"
            suffix = "%"
        elif kpi == "discount_rate":
            numerator = get_total("discounts")
            denominator = get_total("gross_sales")
            label = "Discount Rate"
            suffix = "%"
        elif kpi == "cogs_ratio":
            numerator = get_total("cogs")
            denominator = get_total("sales")
            label = "COGS Ratio"
            suffix = "%"
        elif kpi == "revenue_per_unit":
            numerator = get_total("sales")
            denominator = get_total("units_sold")
            label = "Revenue Per Unit"
            suffix = None
        else:
            return {
                "answer": "Unsupported financial KPI.",
                "rows": [],
                "source": "financials",
                "tool_name": function_name,
            }

        if numerator is None or denominator is None:
            return {
                "answer": "There is not enough matching financial data to calculate this KPI.",
                "rows": [],
                "group_by": "kpi",
                "metric": kpi,
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": country,
                "product": product,
                "segment": segment,
            }

        if denominator == 0:
            return {
                "answer": f"{label} cannot be calculated because the denominator is zero.",
                "rows": [],
                "group_by": "kpi",
                "metric": kpi,
                "source": "financials",
                "tool_name": function_name,
                "year": year,
                "country": country,
                "product": product,
                "segment": segment,
            }

        if suffix == "%":
            value = (numerator / denominator) * 100
            formatted_value = f"{value:.2f}%"
        else:
            value = numerator / denominator
            formatted_value = format_number(value)

        filter_parts = []
        if country:
            filter_parts.append(f"for {country}")
        if product:
            filter_parts.append(f"for product {product}")
        if segment:
            filter_parts.append(f"for segment {segment}")
        if year:
            filter_parts.append(f"in {year}")

        filter_text = " " + " ".join(filter_parts) if filter_parts else ""
        answer = f"{label}{filter_text} is {formatted_value}."

        return {
            "answer": answer,
            "rows": [{"group_name": label, "value": round(value, 2)}],
            "group_by": "kpi",
            "metric": kpi,
            "source": "financials",
            "tool_name": function_name,
            "year": year,
            "country": country,
            "product": product,
            "segment": segment,
            "kpi_value": value,
        }

    # ========================================================
    # RANKING AND CONTRIBUTION ANALYSIS
    # ========================================================

    if function_name == "get_ranking_contribution":

        metric = arguments["metric"]
        group_by = arguments["group_by"]

        limit = max(
            1,
            min(int(arguments.get("limit") or 5), 20)
        )

        filters = {
            "year": arguments.get("year"),
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
        }

        ranking = get_financial_summary(
            metric=metric,
            group_by=group_by,
            limit=limit,
            **filters,
        )

        total_result = get_financial_summary(
            metric=metric,
            group_by="total",
            limit=1,
            **filters,
        )

        ranking_rows = ranking.get("rows", [])
        total_rows = total_result.get("rows", [])

        if not ranking_rows or not total_rows:
            return {
                "answer": "No matching ranking data was found.",
                "rows": [],
                "group_by": group_by,
                "metric": metric,
                "tool_name": function_name,
                "source": "financials",
                **filters,
            }

        total_value = number_to_float(
            total_rows[0]["value"]
        )

        if total_value == 0:
            return {
                "answer": (
                    "Contribution percentages cannot be calculated "
                    "because the selected total is zero."
                ),
                "rows": [],
                "group_by": group_by,
                "metric": metric,
                "tool_name": function_name,
                "source": "financials",
                **filters,
            }

        rows = []

        for index, item in enumerate(
            ranking_rows,
            start=1
        ):

            value = number_to_float(
                item["value"]
            )

            percentage = (
                value / total_value
            ) * 100

            rows.append({
                "rank": index,
                "group_name": item["group_name"],
                "value": round(value, 2),
                "contribution_percent": round(
                    percentage, 2
                )
            })

        first = rows[0]

        answer = (
            f"Showing the top {len(rows)} "
            f"{group_by} results by "
            f"{metric.replace('_', ' ')}. "
            f"The first-ranked result is "
            f"{first['group_name']} with "
            f"{format_number(first['value'])}, "
            f"representing "
            f"{first['contribution_percent']:.2f}% "
            f"of the selected total."
        )

        return {
            "answer": answer,
            "rows": rows,
            "group_by": group_by,
            "metric": metric,
            "tool_name": function_name,
            "source": "financials",
            "total_value": total_value,
            **filters,
        }

    # ==========================================================
    # MONTHLY TREND ANALYSIS
    # ==========================================================

    if function_name == "get_monthly_trend":

        metric = arguments.get("metric", "sales")
        year = arguments.get("year")

        month_order = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        # A single year is required because the existing
        # monthly summary uses month names without
        # necessarily preserving year-month identity.
        if year is None:
            return {
                "answer": (
                    "Please specify a year for the monthly trend."
                ),
                "rows": [],
                "group_by": "month",
                "metric": metric,
                "source": "financials",
                "tool_name": function_name,
            }

        result = get_financial_summary(
            metric=metric,
            group_by="month",
            year=year,
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            limit=20,
        )

        source_rows = result.get("rows", [])

        monthly_rows = []

        for row in source_rows:
            label = str(
                row.get("group_name")
                or row.get("month_name")
                or row.get("month")
                or ""
            ).strip()

            month_num = month_order.get(label.lower())

            if month_num is None:
                month_num = {
                    name[:3]: number
                    for name, number in month_order.items()
                }.get(label.lower()[:3])

            if month_num is None:
                continue

            raw_value = row.get("value")

            if raw_value is None:
                continue

            monthly_rows.append({
                "month_number": month_num,
                "group_name": label,
                "value": float(raw_value),
            })

        monthly_rows.sort(
            key=lambda item: item["month_number"]
        )

        if len(monthly_rows) < 2:
            return {
                "answer": (
                    "There is not enough monthly data "
                    "to determine the trend."
                ),
                "rows": [],
                "group_by": "month",
                "metric": metric,
                "source": "financials",
                "tool_name": function_name,
                "year": year,
            }

        first = monthly_rows[0]
        last = monthly_rows[-1]

        difference = last["value"] - first["value"]

        if difference > 0:
            direction = "upward"
        elif difference < 0:
            direction = "downward"
        else:
            direction = "flat"

        highest = max(
            monthly_rows,
            key=lambda item: item["value"]
        )

        lowest = min(
            monthly_rows,
            key=lambda item: item["value"]
        )

        readable_metric = metric.replace("_", " ").title()

        answer = (
            f"{readable_metric} had a net {direction} "
            f"change from {first['group_name']} to "
            f"{last['group_name']} in {year}. "
            f"The highest monthly value occurred in "
            f"{highest['group_name']}, and the lowest "
            f"in {lowest['group_name']}. "
            "Individual months may have moved in "
            "different directions."
        )

        return {
            "answer": answer,
            "rows": [
                {
                    "group_name": item["group_name"],
                    "value": item["value"],
                }
                for item in monthly_rows
            ],
            "group_by": "month",
            "metric": metric,
            "source": "financials",
            "tool_name": function_name,
            "year": year,
            "country": arguments.get("country"),
            "product": arguments.get("product"),
            "segment": arguments.get("segment"),
            "trend_direction": direction,
        }

    else:
        return {
            "answer": "Unsupported financial reporting operation.",
            "rows": [],
            "tool_name": function_name,
        }
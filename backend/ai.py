import os
import json

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

TOOLS = [
    FINANCIAL_SUMMARY_TOOL,
    FINANCIAL_COMPARISON_TOOL,
    PERCENTAGE_TOOL,
    FINANCIAL_STATISTICS_TOOL,
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
            "content": SYSTEM_PROMPT + context_text,
        }
    ]

    if history:
        for item in history[-8:]:
            role = item.get("role")
            content = item.get("content")

            if (
                role in {"user", "assistant"}
                and content
            ):
                messages.append({
                    "role": role,
                    "content": content,
                })

    messages.append({
        "role": "user",
        "content": question,
    })

    # ========================================================
    # ASK GROQ
    # ========================================================

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0,
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
        }

    # --------------------------------------------------------
    # UNKNOWN TOOL
    # --------------------------------------------------------

    return {
        "answer": (
            "Unsupported financial reporting operation."
        ),
        "rows": [],
    }

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

    tool_call = (
        assistant_message.tool_calls[0]
    )

    function_name = (
        tool_call.function.name
    )

    arguments = json.loads(
        tool_call.function.arguments
    )

    context_text = ""

    if context:
        context_text = f"""

MOST RECENT ANALYSIS CONTEXT

metric: {context.get("metric")}
group_by: {context.get("group_by")}
entity: {context.get("entity")}

For follow-up questions, preserve this context unless
the user explicitly changes it.

If the user says "it", "this", or "that",
the most recent entity is:

{context.get("entity")}

If the user says "compare it with X",
preserve:

metric = {context.get("metric")}
group_by = {context.get("group_by")}

and compare:

{context.get("entity")} with X.
"""

    # Always initialize the follow-up message list before
    # appending history and the latest user question.
    messages: list[dict] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + context_text,
        }
    ]


    if history:
        for item in history[-8:]:
            role = item.get("role")
            content = item.get("content")

            if role in {"user", "assistant"} and content:
                messages.append({
                    "role": role,
                    "content": content,
                })

    messages.append({
        "role": "user",
        "content": question,
    })

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
            year=arguments.get(
                "year"
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
            limit=arguments.get(
                "limit",
                20,
            ),
        )

        return {
            "answer": (
                format_summary_answer(
                    result
                )
            ),
            "rows": result["rows"],
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
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
            "answer": (
                format_comparison_answer(
                    result
                )
            ),
            "rows": result["rows"],
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
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
                "selected_value": result["selected_value"],
                "total_value": result["total_value"],
                "percentage": round(
                    number_to_float(
                        result["percentage"]
                    ),
                    2,
                ),
            }
        ]

        return {
            "answer": (
                format_percentage_answer(
                    result
                )
            ),
            "rows": rows,
            "group_by": result["group_by"],
            "metric": result["metric"],
            "source": "financials",
        }

    if function_name == "get_financial_statistics":
        result = get_financial_statistics(
            metric=arguments["metric"],
            aggregation=arguments["aggregation"],
            group_by=arguments["group_by"],
            year=arguments.get("year"),
            from_date=arguments.get("from_date"),
            to_date=arguments.get("to_date"),
            country=arguments.get("country"),
            product=arguments.get("product"),
            segment=arguments.get("segment"),
            order=arguments.get("order", "highest"),
            limit=arguments.get("limit", 20),
        )

        rows = result["rows"]
        readable_metric = result["metric"].replace("_", " ")
        readable_aggregation = result["aggregation"]

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
        }

    # --------------------------------------------------------
    # UNKNOWN TOOL
    # --------------------------------------------------------

    return {
        "answer": (
            "Unsupported financial reporting operation."
        ),
        "rows": [],
    }
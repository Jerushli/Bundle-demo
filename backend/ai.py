import os
import json
import sys
import re

from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from backend.reporting import get_order_summary


# --------------------------------------------------
# ENVIRONMENT CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)


# --------------------------------------------------
# CREATE GROQ CLIENT
# --------------------------------------------------

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing from backend/.env"
    )

client = Groq(
    api_key=GROQ_API_KEY,
    timeout=30.0
)


# --------------------------------------------------
# DEFINE TOOL FOR AI
# --------------------------------------------------

REPORTING_TOOL = {
    "type": "function",

    "function": {

        "name": "get_order_summary",

        "description": (
            "Retrieve real order counts from the PostgreSQL "
            "database. Use this tool whenever the user asks "
            "about order totals, orders by provider, "
            "or orders by date."
        ),

        "parameters": {

            "type": "object",

            "properties": {

                "from_date": {
                    "type": "string",
                    "description": (
                        "Start date in YYYY-MM-DD format."
                    )
                },

                "to_date": {
                    "type": "string",
                    "description": (
                        "End date in YYYY-MM-DD format."
                    )
                },

                "group_by": {
                    "type": "string",
                    "enum": [
                        "total",
                        "provider",
                        "date"
                    ],
                    "description": (
                        "How the order results should be grouped."
                    )
                },

                "provider": {
                    "type": "string",
                    "description": (
                        "Optional provider name, such as Alpha or Beta."
                    )
                }

            },

            "required": [
                "from_date",
                "to_date",
                "group_by"
            ]
        }
    }
}


# --------------------------------------------------
# SYSTEM INSTRUCTIONS
# --------------------------------------------------

SYSTEM_PROMPT = """
You are Bundle Data Assistant.

You help users retrieve order information from
a PostgreSQL database.

Available reporting operations:

1. Total orders.
2. Orders grouped by provider.
3. Orders grouped by date.
4. Orders filtered by provider.

Use get_order_summary whenever the user asks
a question requiring order data.

Do not invent database numbers.

The demo database contains records for
September 1 through September 3, 2026.

If the user asks about all orders without specifying
dates, use:

from_date: 2026-09-01
to_date: 2026-09-03

For questions such as:
"How many orders are there?"

Use group_by: total.

For questions such as:
"Show orders by provider"

Use group_by: provider.

For questions such as:
"Show orders by date"

Use group_by: date.

For questions such as:
"How many orders did Alpha receive?"

Use provider: Alpha
and group_by: total.

Keep answers clear and concise.

IMPORTANT DATE RULES:

Always preserve the dates explicitly provided by the user.

Never silently change, reverse, correct, or replace
an invalid date range.

Only use the default date range when the user does
not specify any dates.

If the user provides a start date that comes after
the end date, do not execute a reporting tool.

Explain that the start date must be before or
equal to the end date.

If the user's date range is unclear, ask for clarification.
"""

def validate_question_date_range(question: str):

    pattern = (
        r"\b"
        r"(?P<month>"
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
        r")"
        r"\s+"
        r"(?P<start_day>\d{1,2})"
        r"\s+to\s+"
        r"(?P<end_day>\d{1,2})"
        r",?\s+"
        r"(?P<year>\d{4})"
        r"\b"
    )

    match = re.search(
        pattern,
        question,
        re.IGNORECASE
    )

    if not match:
        return

    month = datetime.strptime(
        match.group("month"),
        "%B"
    ).month

    year = int(match.group("year"))

    start = date(
        year,
        month,
        int(match.group("start_day"))
    )

    end = date(
        year,
        month,
        int(match.group("end_day"))
    )

    if start > end:

        raise ValueError(
            "The start date cannot be after the end date."
        )

# --------------------------------------------------
# AI CHAT FUNCTION
# --------------------------------------------------

def process_chat(question: str):
        
    validate_question_date_range(question)

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "user",
            "content": question
        }

    ]

    # Ask Groq to understand the user's question.

    response = client.chat.completions.create(

        model=GROQ_MODEL,

        messages=messages,

        tools=[REPORTING_TOOL],

        tool_choice="auto",

        temperature=0

    )

    assistant_message = response.choices[0].message

    # Check whether the AI selected a tool.

    if assistant_message.tool_calls:

        tool_call = assistant_message.tool_calls[0]

        function_name = tool_call.function.name

        # Only execute our approved reporting function.

        if function_name != "get_order_summary":

            return {
                "answer": "Unsupported reporting operation.",
                "rows": []
            }

        # Convert the AI's JSON arguments to Python values.

        arguments = json.loads(
            tool_call.function.arguments
        )


        # Execute the reporting function.

        result = get_order_summary(
            from_date=arguments["from_date"],
            to_date=arguments["to_date"],
            group_by=arguments["group_by"],
            provider=arguments.get("provider")
        )

        # Prepare a deterministic answer using actual DB results.

        rows = result["rows"]

        group_by = result["group_by"]

        if group_by == "total":

            if not rows:

                answer = (
                    "No orders found between "
                    f"{result['from_date']} "
                    f"and {result['to_date']}."
                )

            else:
                total = rows[0]["total_orders"]

                if total == 0:

                    answer = (
                        "No orders found between "
                        f"{result['from_date']} "
                        f"and {result['to_date']}."
                    )

                else:

                    answer = (
                        f"There are {total} orders "
                        f"between {result['from_date']} "
                        f"and {result['to_date']}."
                    )

        elif group_by == "provider":

            if not rows:

                answer = (
                    "No orders found for the selected period."
                )

            else:

                total = sum(
                    row["total_orders"]
                    for row in rows
                )

                answer = (
                    f"Found {total} orders "
                    f"across {len(rows)} provider(s)."
                )

        else:

            if not rows:

                answer = (
                    "No orders found for the selected period."
                )

            else:

                total = sum(
                    row["total_orders"]
                    for row in rows
                )

                answer = (
                    f"Found {total} orders "
                    f"across {len(rows)} date(s)."
                )

        return {
            "answer": answer,
            "rows": rows,
            "group_by": group_by
        }

    # No reporting tool was selected.

    return {
        "answer": (
            assistant_message.content
            or "I can help with order reporting questions."
        ),
        "rows": []
    }


# --------------------------------------------------
# PRINT UTILITY
# --------------------------------------------------

class print:
    """A small, useful console-print helper with a print-like API."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout

    def write(self, value):
        text = "" if value is None else str(value)
        self.stream.write(text)
        return len(text)

    def flush(self):
        if hasattr(self.stream, "flush"):
            self.stream.flush()
        return None

    def emit(self, *values, sep=" ", end="\n", flush=False):
        text = sep.join("" if value is None else str(value) for value in values)
        self.write(text + end)
        if flush:
            self.flush()
        return text + end

    def __call__(self, *values, sep=" ", end="\n", flush=False):
        return self.emit(*values, sep=sep, end=end, flush=flush)
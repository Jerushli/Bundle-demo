from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.dcf_chat import (
    _extract_discount_rate,
    _extract_initial_investment,
    _extract_periodic_cash_flow,
    _extract_periods_and_unit,
    _extract_terminal_value,
    _extract_working_capital_outflow,
    _extract_working_capital_recovery,
)
from backend.dcf_engine import (
    dcf_result_to_dict,
)
from backend.finance_metrics import (
    advanced_metrics_to_dict,
    calculate_advanced_finance_metrics,
)


load_dotenv(
    override=True
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing."
    )

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

client = Groq(
    api_key=GROQ_API_KEY.strip(),
    timeout=30.0,
)


ADVANCED_FINANCE_MARKERS = (
    "irr",
    "internal rate of return",
    "profitability index",
    "return multiple",
    "simple roi",
    "discounted payback",
    "advanced finance",
    "advanced investment metrics",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def should_use_advanced_finance(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    return any(
        marker in q
        for marker in ADVANCED_FINANCE_MARKERS
    )


def _requirements(
    *,
    question: str,
    missing: list[str],
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**Advanced finance analysis needs more explicit assumptions.** "
            "I will not invent the missing values. Please provide: "
            + ", ".join(
                missing
            )
            + ". Terminal value and working-capital assumptions are optional "
            "and default to zero when omitted."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "advanced_finance",
        "tool_name": (
            "advanced_finance_requirements"
        ),
        "answer_mode": answer_mode,
        "advanced_finance": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
        },
    }


def _fallback_answer(
    *,
    dcf: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    irr_status = metrics.get(
        "irr_status"
    )

    irr = metrics.get(
        "irr_annualized_percent"
    )

    if (
        irr_status == "available"
        and irr is not None
    ):
        irr_text = (
            f"{float(irr):.2f}% annualized IRR"
        )

    else:
        irr_text = (
            f"IRR status: {irr_status}"
        )

    pi = metrics.get(
        "profitability_index"
    )

    pi_text = (
        f"{float(pi):.3f}"
        if pi is not None
        else "not available"
    )

    return (
        f"**Advanced finance result:** NPV is {float(dcf['npv']):,.2f}; "
        f"{irr_text}; profitability index is {pi_text}. "
        f"Simple payback is {metrics.get('simple_payback_periods')} periods and "
        f"discounted payback is {metrics.get('discounted_payback_periods')} periods. "
        "These results are deterministic calculations from the supplied cash-flow "
        "assumptions, not predictions of future performance."
    )


def _explain(
    *,
    question: str,
    dcf: dict[str, Any],
    metrics: dict[str, Any],
    answer_mode: str,
) -> str:
    style = (
        "Give a concise executive explanation in 6 to 8 sentences."
        if answer_mode
        == "summary"
        else (
            "Give a detailed explanation with sections for Cash-Flow Assumptions, "
            "NPV, IRR, Profitability Index, ROI / Return Multiple, Payback, "
            "Interpretation Risks, and Bottom Line."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining deterministic investment metrics.

Rules:
1. Use the deterministic numbers exactly as supplied.
2. Do not recalculate or alter NPV, IRR, profitability index, ROI, or payback.
3. Clearly state that future cash flows, terminal value, working capital, and
   discount rate are supplied assumptions rather than predictions.
4. Explain NPV as absolute value created/destroyed at the supplied discount rate.
5. Explain IRR as the break-even discount rate of the supplied cash-flow series.
6. If irr_status is not "available", do not invent an IRR.
7. If irr_status is "ambiguous", explain that multiple sign changes can produce
   multiple IRRs and Bundle intentionally does not report one number.
8. Simple ROI ignores timing; NPV and IRR account for timing.
9. Profitability index above 1 means PV of future cash flows exceeds initial
   outflow under the supplied assumptions; below 1 means it does not.
10. Do not invent tax, inflation, financing, depreciation, risk premiums, or
    other metrics absent from the deterministic result.
11. Do not claim management should automatically approve or reject an investment.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

DCF RESULT

{json.dumps(dcf, ensure_ascii=False, indent=2)}

ADVANCED METRICS

{json.dumps(metrics, ensure_ascii=False, indent=2)}
""".strip()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0,
        )

        answer = (
            response.choices[0]
            .message.content
            or ""
        ).strip()

        if answer:
            return answer

    except Exception:
        pass

    return _fallback_answer(
        dcf=dcf,
        metrics=metrics,
    )


def process_advanced_finance_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    initial_investment = (
        _extract_initial_investment(
            question
        )
    )

    periodic_cash_flow = (
        _extract_periodic_cash_flow(
            question
        )
    )

    periods, period_unit = (
        _extract_periods_and_unit(
            question
        )
    )

    discount_rate = (
        _extract_discount_rate(
            question
        )
    )

    terminal_value = (
        _extract_terminal_value(
            question
        )
    )

    working_capital_outflow = (
        _extract_working_capital_outflow(
            question
        )
    )

    working_capital_recovery = (
        _extract_working_capital_recovery(
            question
        )
    )

    missing: list[str] = []

    if initial_investment is None:
        missing.append(
            "initial investment amount"
        )

    if periodic_cash_flow is None:
        missing.append(
            "recurring periodic cash-flow amount"
        )

    if (
        periods is None
        or period_unit is None
    ):
        missing.append(
            "modeled duration in months or years"
        )

    if discount_rate is None:
        missing.append(
            "annual discount rate percentage"
        )

    if missing:
        return _requirements(
            question=question,
            missing=missing,
            answer_mode=answer_mode,
        )

    dcf_result, metrics = (
        calculate_advanced_finance_metrics(
            initial_investment=float(
                initial_investment
            ),
            periodic_cash_flow=float(
                periodic_cash_flow
            ),
            periods=int(
                periods
            ),
            annual_discount_rate_percent=float(
                discount_rate
            ),
            period_unit=period_unit,
            working_capital_outflow=float(
                working_capital_outflow
            ),
            working_capital_recovery=float(
                working_capital_recovery
            ),
            terminal_value=float(
                terminal_value
            ),
        )
    )

    dcf_payload = dcf_result_to_dict(
        dcf_result
    )

    metrics_payload = advanced_metrics_to_dict(
        metrics
    )

    rows = [
        {
            "group_name": "NPV",
            "value": dcf_result.npv,
        },
        {
            "group_name": (
                "Profitability index"
            ),
            "value": (
                metrics.profitability_index
                if metrics.profitability_index
                is not None
                else 0
            ),
        },
        {
            "group_name": (
                "Annualized IRR %"
            ),
            "value": (
                metrics.irr_annualized_percent
                if metrics.irr_annualized_percent
                is not None
                else 0
            ),
        },
    ]

    return {
        "answer": _explain(
            question=question,
            dcf=dcf_payload,
            metrics=metrics_payload,
            answer_mode=answer_mode,
        ),
        "rows": rows,
        "group_by": (
            "advanced_finance"
        ),
        "metric": "finance_metric",
        "source": (
            "advanced_finance"
        ),
        "tool_name": (
            "finance_metrics"
        ),
        "answer_mode": answer_mode,
        "dcf": dcf_payload,
        "advanced_finance": (
            metrics_payload
        ),
        "evidence": {
            "dcf": dcf_payload,
            "advanced_metrics": (
                metrics_payload
            ),
        },
    }

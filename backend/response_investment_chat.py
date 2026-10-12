from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from backend.business_rules import (
    get_investment_policy,
)
from backend.investment_chat import (
    _extract_baseline_period,
    _extract_horizon,
    _extract_hurdle_rate,
    _extract_investment_amount,
    _extract_margin,
    _extract_max_payback,
    _extract_target,
)
from backend.investment_model import (
    calculate_investment_scenario,
    investment_result_to_dict,
)
from backend.response_model_chat import (
    _detect_relationship,
    _extract_signed_percent,
)
from backend.response_models import (
    estimate_response,
    list_response_models,
    response_estimate_to_dict,
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


MODEL_MARKERS = (
    "validated model",
    "response model",
    "model estimate",
    "model estimates",
)

ECONOMICS_MARKERS = (
    "investment economics",
    "roi",
    "payback",
    "worth it",
    "investment return",
    "investment result",
    "economic result",
    "economics look",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def should_use_response_investment(
    *,
    question: str,
    role: str,
) -> bool:
    q = _normalize(
        question
    )

    has_model_intent = any(
        marker in q
        for marker in MODEL_MARKERS
    )

    has_economics_intent = any(
        marker in q
        for marker in ECONOMICS_MARKERS
    )

    return (
        has_model_intent
        and has_economics_intent
    )



def _resolve_sales_relationship_for_investment(
    *,
    question: str,
    detected_input: str | None,
    detected_output: str | None,
) -> tuple[
    str | None,
    str | None,
    list[dict[str, Any]],
]:
    """
    Stage 20.3 permits only validated models whose output is `sales`.

    If the normal Stage 20.2 detector succeeds, keep that exact relationship.

    If it fails only because the integrated investment question omits the word
    `sales`, resolve a unique validated input -> sales relationship by matching
    the registered input variable against the question.

    Never guess when more than one distinct input -> sales relationship matches.
    """
    if (
        detected_input is not None
        and detected_output is not None
    ):
        return (
            detected_input,
            detected_output,
            [],
        )

    q = _normalize(
        question
    )

    models = list_response_models(
        validation_status="validated",
    )

    matches: dict[
        tuple[str, str],
        list[Any],
    ] = {}

    for model in models:
        if model.output_variable != "sales":
            continue

        input_phrases = {
            model.input_variable.lower(),
            model.input_variable.lower().replace("_", " "),
            model.input_variable.lower().replace("-", " "),
        }

        input_present = any(
            " ".join(
                phrase.split()
            ) in q
            for phrase in input_phrases
            if phrase
        )

        if not input_present:
            continue

        key = (
            model.input_variable,
            model.output_variable,
        )

        matches.setdefault(
            key,
            [],
        ).append(
            model
        )

    if len(matches) == 1:
        input_variable, output_variable = next(
            iter(
                matches.keys()
            )
        )

        return (
            input_variable,
            output_variable,
            [],
        )

    candidates = [
        {
            "input_variable": key[0],
            "output_variable": key[1],
            "model_count": len(
                values
            ),
        }
        for key, values in matches.items()
    ]

    return (
        None,
        None,
        candidates,
    )


def _requirements(
    *,
    question: str,
    missing: list[str],
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**Validated-model investment analysis needs more explicit inputs.** "
            "I will not invent the missing values. Please provide: "
            + ", ".join(
                missing
            )
            + "."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "response_investment",
        "tool_name": (
            "response_investment_requirements"
        ),
        "answer_mode": answer_mode,
        "response_investment": {
            "supported": False,
            "question": question,
            "missing_inputs": missing,
        },
    }


def _unsupported_output(
    *,
    question: str,
    output_variable: str,
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**The validated response model cannot yet be connected safely "
            "to the investment engine.** "
            f"Stage 20.3 only supports a validated `sales` response, but the "
            f"resolved output variable is `{output_variable}`. Bundle will not "
            "silently convert that variable into revenue or profit."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "response_investment",
        "tool_name": (
            "response_investment_unsupported"
        ),
        "answer_mode": answer_mode,
        "response_investment": {
            "supported": False,
            "question": question,
            "output_variable": output_variable,
            "reason": (
                "Only validated sales-response models are supported by the "
                "Stage 20.3 investment bridge."
            ),
        },
    }


def _unavailable_model(
    *,
    question: str,
    message: str,
    answer_mode: str,
) -> dict[str, Any]:
    return {
        "answer": (
            "**No applicable validated response model is available.** "
            f"{message} Bundle will not replace it with a guessed uplift. "
            "Use an explicit scenario assumption instead or validate an "
            "appropriate response model."
        ),
        "rows": [],
        "group_by": None,
        "metric": None,
        "source": "response_investment",
        "tool_name": (
            "response_investment_model_unavailable"
        ),
        "answer_mode": answer_mode,
        "response_investment": {
            "supported": False,
            "question": question,
            "reason": message,
        },
    }


def _fallback_answer(
    *,
    response_estimate: dict[str, Any],
    investment: dict[str, Any],
) -> str:
    return (
        f"The registered validated model **{response_estimate['model_name']} "
        f"v{response_estimate['version']}** estimates a "
        f"{response_estimate['estimated_output_change_percent']:.2f}% change "
        f"in sales for the supplied "
        f"{response_estimate['input_change_percent']:.2f}% input change. "
        f"Using that model estimate as the investment engine's sales-response "
        f"input, Bundle calculates incremental operating profit of "
        f"{investment['incremental_operating_profit']:,.2f}, scenario ROI of "
        f"{investment['roi_percent']:.2f}%, and payback of "
        f"{investment['payback_months'] if investment['payback_months'] is not None else 'not achieved'} "
        f"months. The rule result is "
        f"{investment['rule_result'].replace('_', ' ')}. "
        "The sales response remains a model estimate, not an observed outcome "
        "or guaranteed causal effect."
    )


def _explain(
    *,
    question: str,
    response_estimate: dict[str, Any],
    investment: dict[str, Any],
    business_rules: dict[str, Any],
    answer_mode: str,
) -> str:
    style = (
        "Give a concise executive explanation in 7 to 9 sentences."
        if answer_mode == "summary"
        else (
            "Give a detailed explanation with sections for Requested Change, "
            "Validated Response Model, Estimated Sales Response, Live Baseline, "
            "Investment Economics, Governed Rules, Evidence Chain, "
            "Causality / Model Risk, and Bottom Line."
        )
    )

    system_prompt = """
You are Bundle Data Assistant explaining an investment analysis that uses a
registered validated response-model estimate.

Rules:
1. Use every deterministic number exactly as supplied.
2. Explicitly preserve this evidence chain:
   validated response model -> estimated sales response -> live database
   baseline -> deterministic investment calculation.
3. The sales uplift is a MODEL ESTIMATE, not a user assumption and not an
   observed result.
4. Do not call the model causal unless the supplied metadata proves a causal
   identification method; validation alone does not prove causality.
5. Contribution margin and investment amount remain explicit scenario inputs.
6. State ROI/payback only as scenario economics under these inputs.
7. State which governed hurdle/payback rules were applied.
8. Do not invent NPV, IRR, tax, financing, or downstream effects.
9. Passing investment rules does not authorize management action.
10. Mention model confidence/provenance and that extrapolation/model drift may
    make the response estimate unreliable.
""".strip()

    user_prompt = f"""
QUESTION

{question}

STYLE

{style}

VALIDATED RESPONSE ESTIMATE

{json.dumps(response_estimate, ensure_ascii=False, indent=2, default=str)}

DETERMINISTIC INVESTMENT RESULT

{json.dumps(investment, ensure_ascii=False, indent=2, default=str)}

GOVERNED BUSINESS RULES

{json.dumps(business_rules, ensure_ascii=False, indent=2, default=str)}
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
        response_estimate=response_estimate,
        investment=investment,
    )


def process_response_investment_chat(
    *,
    question: str,
    role: str,
    answer_mode: str = "summary",
) -> dict[str, Any]:
    (
        detected_input,
        detected_output,
        detected_candidates,
    ) = _detect_relationship(
        question
    )

    (
        input_variable,
        output_variable,
        bridge_candidates,
    ) = _resolve_sales_relationship_for_investment(
        question=question,
        detected_input=detected_input,
        detected_output=detected_output,
    )

    candidates = (
        bridge_candidates
        or detected_candidates
    )

    input_change_percent = (
        _extract_signed_percent(
            question
        )
    )

    target_column, target_value = (
        _extract_target(
            question=question,
            role=role,
        )
    )

    investment_amount = (
        _extract_investment_amount(
            question
        )
    )

    margin = (
        _extract_margin(
            question
        )
    )

    horizon = (
        _extract_horizon(
            question
        )
    )

    baseline_period = (
        _extract_baseline_period(
            question
        )
    )

    requested_hurdle = (
        _extract_hurdle_rate(
            question
        )
    )

    requested_payback = (
        _extract_max_payback(
            question
        )
    )

    missing: list[str] = []

    if (
        input_variable is None
        or output_variable is None
    ):
        missing.append(
            "one unambiguous validated input → output relationship"
        )

    if input_change_percent is None:
        missing.append(
            "explicit input change percentage"
        )

    if (
        target_column is None
        or target_value is None
    ):
        missing.append(
            "one specific investment target such as a region"
        )

    if investment_amount is None:
        missing.append(
            "investment amount"
        )

    if margin is None:
        missing.append(
            "incremental/contribution margin percentage"
        )

    if horizon is None:
        missing.append(
            "investment horizon in months"
        )

    if missing:
        response = _requirements(
            question=question,
            missing=missing,
            answer_mode=answer_mode,
        )

        response[
            "response_investment"
        ][
            "candidate_relationships"
        ] = candidates

        return response

    if output_variable != "sales":
        return _unsupported_output(
            question=question,
            output_variable=output_variable,
            answer_mode=answer_mode,
        )

    try:
        estimate = estimate_response(
            input_variable=input_variable,
            output_variable=output_variable,
            input_change_percent=float(
                input_change_percent
            ),
            scope_type=target_column,
            scope_value=target_value,
        )

    except ValueError as exc:
        return _unavailable_model(
            question=question,
            message=str(
                exc
            ),
            answer_mode=answer_mode,
        )

    response_payload = (
        response_estimate_to_dict(
            estimate
        )
    )

    policy = get_investment_policy(
        target_column=target_column,
        target_value=target_value,
    )

    policy_hurdle = float(
        policy[
            "hurdle_rate_percent"
        ]
    )

    policy_payback = float(
        policy[
            "max_payback_months"
        ]
    )

    policy_baseline = int(
        policy[
            "default_baseline_period_months"
        ]
    )

    effective_baseline = (
        int(
            baseline_period
        )
        if baseline_period
        is not None
        else policy_baseline
    )

    effective_hurdle = (
        max(
            float(
                requested_hurdle
            ),
            policy_hurdle,
        )
        if requested_hurdle
        is not None
        else policy_hurdle
    )

    effective_payback = (
        min(
            float(
                requested_payback
            ),
            policy_payback,
        )
        if requested_payback
        is not None
        else policy_payback
    )

    investment_result = (
        calculate_investment_scenario(
            role=role,
            target_column=target_column,
            target_value=target_value,
            investment_amount=float(
                investment_amount
            ),
            expected_revenue_uplift_percent=float(
                estimate.estimated_output_change_percent
            ),
            contribution_margin_percent=float(
                margin
            ),
            horizon_months=int(
                horizon
            ),
            baseline_period_months=(
                effective_baseline
            ),
            hurdle_rate_percent=(
                effective_hurdle
            ),
            max_payback_months=(
                effective_payback
            ),
            baseline_measure="sales",
        )
    )

    investment_payload = (
        investment_result_to_dict(
            investment_result
        )
    )

    business_rules = {
        "policy": {
            "hurdle_rate_percent": (
                policy_hurdle
            ),
            "max_payback_months": (
                policy_payback
            ),
            "default_baseline_period_months": (
                policy_baseline
            ),
            "resolved_rules": policy.get(
                "resolved_rules",
                {},
            ),
        },
        "requested": {
            "hurdle_rate_percent": (
                requested_hurdle
            ),
            "max_payback_months": (
                requested_payback
            ),
            "baseline_period_months": (
                baseline_period
            ),
        },
        "effective": {
            "hurdle_rate_percent": (
                effective_hurdle
            ),
            "max_payback_months": (
                effective_payback
            ),
            "baseline_period_months": (
                effective_baseline
            ),
        },
    }

    evidence_chain = {
        "step_1": {
            "type": (
                "registered_validated_response_model"
            ),
            "model_id": (
                estimate.model_id
            ),
            "model_name": (
                estimate.model_name
            ),
            "version": (
                estimate.version
            ),
            "confidence_level": (
                estimate.confidence_level
            ),
        },
        "step_2": {
            "type": (
                "model_estimated_sales_response"
            ),
            "input_change_percent": (
                estimate.input_change_percent
            ),
            "estimated_sales_change_percent": (
                estimate.estimated_output_change_percent
            ),
        },
        "step_3": {
            "type": (
                "live_database_sales_baseline"
            ),
            "dataset_name": (
                investment_result.dataset_name
            ),
            "target_column": (
                investment_result.target_column
            ),
            "target_value": (
                investment_result.target_value
            ),
            "baseline_sales": (
                investment_result.baseline_value
            ),
        },
        "step_4": {
            "type": (
                "deterministic_investment_model"
            ),
            "incremental_revenue": (
                investment_result.incremental_revenue
            ),
            "incremental_operating_profit": (
                investment_result.incremental_operating_profit
            ),
            "roi_percent": (
                investment_result.roi_percent
            ),
            "payback_months": (
                investment_result.payback_months
            ),
            "rule_result": (
                investment_result.rule_result
            ),
        },
    }

    rows = [
        {
            "group_name": (
                "Model estimated sales change %"
            ),
            "value": (
                estimate.estimated_output_change_percent
            ),
        },
        {
            "group_name": (
                "Incremental operating profit"
            ),
            "value": (
                investment_result.incremental_operating_profit
            ),
        },
        {
            "group_name": "ROI %",
            "value": (
                investment_result.roi_percent
            ),
        },
    ]

    return {
        "answer": _explain(
            question=question,
            response_estimate=(
                response_payload
            ),
            investment=(
                investment_payload
            ),
            business_rules=(
                business_rules
            ),
            answer_mode=answer_mode,
        ),
        "rows": rows,
        "group_by": (
            "response_investment"
        ),
        "metric": (
            "mixed_finance"
        ),
        "source": (
            "response_investment"
        ),
        "tool_name": (
            "response_model_investment_bridge"
        ),
        "answer_mode": answer_mode,
        "response_model": (
            response_payload
        ),
        "investment": (
            investment_payload
        ),
        "business_rules": (
            business_rules
        ),
        "evidence_chain": (
            evidence_chain
        ),
        "evidence": {
            "response_model": (
                response_payload
            ),
            "investment": (
                investment_payload
            ),
            "business_rules": (
                business_rules
            ),
            "evidence_chain": (
                evidence_chain
            ),
        },
    }

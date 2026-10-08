from __future__ import annotations

import re
from statistics import mean
from typing import Any

from backend.dataset_analytics import (
    execute_dataset_analysis,
    get_active_dataset_schema,
    get_category_value_matches,
)
from backend.dataset_profiles import (
    get_latest_business_profile,
)
from backend.forecast_engine import (
    forecast_monthly_measure,
    forecast_to_dict,
)
from backend.rag_bridge import (
    retrieve_rag_evidence,
)


DECISION_MARKERS = (
    "should we invest",
    "should i invest",
    "should we expand",
    "should we increase budget",
    "should we allocate",
    "worth investing",
    "worth expanding",
    "more budget",
    "invest more",
    "expand more",
)


def _normalize(
    value: str,
) -> str:
    return " ".join(
        value.lower().split()
    )


def is_decision_question(
    question: str,
) -> bool:
    q = _normalize(
        question
    )

    return any(
        marker in q
        for marker in DECISION_MARKERS
    )


def _resolve_target(
    *,
    question: str,
    role: str,
) -> tuple[
    str | None,
    str | None,
]:
    matches = get_category_value_matches(
        question,
        role=role,
    )

    priority = (
        "region",
        "country",
        "product",
        "segment",
        "department",
        "channel",
        "category",
    )

    for column in priority:
        values = matches.get(
            column
        )

        if (
            values
            and len(
                values
            ) == 1
        ):
            return (
                column,
                values[0],
            )

    singles = [
        (
            column,
            values[0],
        )
        for column, values
        in matches.items()
        if len(
            values
        ) == 1
    ]

    if len(
        singles
    ) == 1:
        return singles[0]

    return (
        None,
        None,
    )


def _preferred_measures(
    *,
    measures: list[str],
    dataset_name: str,
) -> list[str]:
    selected: list[str] = []

    for preferred in (
        "sales",
        "revenue",
        "profit",
        "gross_sales",
        "cogs",
    ):
        if (
            preferred in measures
            and preferred not in selected
        ):
            selected.append(
                preferred
            )

    try:
        profile = get_latest_business_profile(
            dataset_name
        )

        primary = profile.get(
            "primary_measure"
        )

        if (
            isinstance(
                primary,
                str,
            )
            and primary in measures
            and primary not in selected
        ):
            selected.insert(
                0,
                primary,
            )

    except Exception:
        pass

    if not selected:
        selected = list(
            measures[:2]
        )

    return selected[:3]


def _numeric_rows(
    rows: list[
        dict[str, Any]
    ],
) -> list[
    dict[str, Any]
]:
    output: list[
        dict[str, Any]
    ] = []

    for row in rows:
        try:
            value = float(
                row.get(
                    "value"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        output.append(
            {
                "group_name": str(
                    row.get(
                        "group_name",
                        ""
                    )
                ),
                "value": value,
            }
        )

    return output


def _measure_evidence(
    *,
    role: str,
    measure: str,
    group_by: str,
    group_value: str,
) -> dict[str, Any]:
    result = execute_dataset_analysis(
        role=role,
        operation="group",
        aggregation="sum",
        measure=measure,
        group_by=group_by,
        limit=100,
    )

    rows = _numeric_rows(
        result.get(
            "rows",
            [],
        )
    )

    if not rows:
        return {
            "measure": measure,
            "available": False,
            "reason": (
                "No grouped numeric rows were returned."
            ),
        }

    target = next(
        (
            row
            for row in rows
            if row[
                "group_name"
            ].lower()
            == group_value.lower()
        ),
        None,
    )

    if target is None:
        return {
            "measure": measure,
            "available": False,
            "reason": (
                f"{group_value!r} was not present in the grouped result."
            ),
        }

    ranked = sorted(
        rows,
        key=lambda row: row[
            "value"
        ],
        reverse=True,
    )

    rank = next(
        index
        for index, row
        in enumerate(
            ranked,
            start=1,
        )
        if row[
            "group_name"
        ].lower()
        == group_value.lower()
    )

    peers = [
        row["value"]
        for row in rows
        if row[
            "group_name"
        ].lower()
        != group_value.lower()
    ]

    peer_average = (
        mean(
            peers
        )
        if peers
        else None
    )

    total = sum(
        row["value"]
        for row in rows
    )

    gap = (
        target["value"]
        - peer_average
        if peer_average is not None
        else None
    )

    gap_percent = None

    if (
        gap is not None
        and peer_average not in (
            None,
            0,
        )
    ):
        gap_percent = (
            gap
            / abs(
                peer_average
            )
            * 100
        )

    return {
        "measure": measure,
        "available": True,
        "target_value": round(
            target["value"],
            2,
        ),
        "rank": rank,
        "group_count": len(
            ranked
        ),
        "peer_average": (
            round(
                peer_average,
                2,
            )
            if peer_average
            is not None
            else None
        ),
        "gap_vs_peer_average": (
            round(
                gap,
                2,
            )
            if gap is not None
            else None
        ),
        "gap_vs_peer_average_percent": (
            round(
                gap_percent,
                2,
            )
            if gap_percent
            is not None
            else None
        ),
        "share_percent": (
            round(
                target["value"]
                / total
                * 100,
                2,
            )
            if total != 0
            else None
        ),
        "leader": ranked[0],
        "rows": ranked,
    }


def _forecast_evidence(
    *,
    role: str,
    measures: list[str],
) -> dict[str, Any]:
    if not measures:
        return {
            "available": False,
            "reason": (
                "No permitted numeric measure is available for forecasting."
            ),
        }

    # Prefer profit for an investment decision when available.
    if "profit" in measures:
        measure = "profit"

    elif "sales" in measures:
        measure = "sales"

    else:
        measure = measures[0]

    try:
        result = forecast_monthly_measure(
            role=role,
            measure=measure,
            date_column=None,
            horizon_months=3,
            lookback_months=24,
        )

        payload = forecast_to_dict(
            result
        )

        return {
            "available": True,
            "scope": "overall_dataset",
            "important_scope_note": (
                "This Stage 15.1 forecast is for the overall active dataset, "
                "not specifically filtered to the decision target."
            ),
            **payload,
        }

    except Exception as exc:
        return {
            "available": False,
            "measure": measure,
            "reason": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


def _rag_evidence(
    *,
    question: str,
    role: str,
    dataset_name: str,
    target_column: str,
    target_value: str,
) -> dict[str, Any]:
    query = (
        f"{question}\n"
        f"Decision target: {target_column}={target_value}\n"
        "Find authorized evidence relevant to performance, customer issues, "
        "operations, risk, demand, delivery, incidents, projects, capacity, "
        "or other factors that may matter to an investment/expansion decision."
    )

    try:
        results = retrieve_rag_evidence(
            question=query,
            role=role,
            dataset_name=dataset_name,
            limit=5,
        )

        return {
            "available": True,
            "count": len(
                results
            ),
            "results": results,
        }

    except Exception as exc:
        return {
            "available": False,
            "count": 0,
            "results": [],
            "reason": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


def _has_currency_amount(
    question: str,
) -> bool:
    q = _normalize(
        question
    )

    return bool(
        re.search(
            r"(?:₹|\$|€|£)\s*\d",
            question,
        )
        or re.search(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:crore|cr|lakh|lakhs|million|billion|m)\b",
            q,
        )
    )


def _has_time_horizon(
    question: str,
) -> bool:
    q = _normalize(
        question
    )

    return bool(
        re.search(
            r"\b(?:next|over|within|for)\s+"
            r"\d+\s+(?:day|days|month|months|quarter|quarters|year|years)\b",
            q,
        )
        or any(
            phrase in q
            for phrase in (
                "next month",
                "next quarter",
                "next year",
                "short term",
                "long term",
            )
        )
    )


def _scenario_readiness(
    question: str,
) -> dict[str, Any]:
    missing: list[str] = []

    if not _has_currency_amount(
        question
    ):
        missing.append(
            "investment amount / budget"
        )

    if not _has_time_horizon(
        question
    ):
        missing.append(
            "decision time horizon"
        )

    missing.extend(
        [
            (
                "validated investment/budget → incremental "
                "sales/profit response relationship"
            ),
            "investment cost structure",
            "required return / hurdle rate",
        ]
    )

    return {
        "quantified_roi_supported": False,
        "reason": (
            "Bundle does not yet have a validated causal model mapping "
            "investment or budget changes to incremental sales/profit."
        ),
        "missing_inputs": missing,
        "safe_outputs_now": [
            "current performance evidence",
            "trend/forecast evidence",
            "authorized document evidence",
            "risk indicators",
            "identification of missing assumptions",
        ],
    }


def _structured_risks(
    structured: dict[
        str,
        Any
    ],
) -> list[str]:
    risks: list[str] = []

    for measure, evidence in structured.get(
        "measures",
        {}
    ).items():
        if not evidence.get(
            "available"
        ):
            continue

        rank = evidence.get(
            "rank"
        )

        count = evidence.get(
            "group_count"
        )

        gap_pct = evidence.get(
            "gap_vs_peer_average_percent"
        )

        if (
            isinstance(
                rank,
                int,
            )
            and isinstance(
                count,
                int,
            )
            and count > 1
            and rank
            > (
                count
                + 1
            )
            / 2
        ):
            risks.append(
                f"{structured['target_value']} ranks "
                f"{rank}/{count} on {measure}."
            )

        if (
            isinstance(
                gap_pct,
                (
                    int,
                    float,
                ),
            )
            and gap_pct < 0
        ):
            risks.append(
                f"{measure} is {abs(gap_pct):.1f}% below "
                "the peer average."
            )

    return risks


def build_decision_evidence(
    *,
    question: str,
    role: str,
) -> dict[str, Any]:
    schema = get_active_dataset_schema(
        role=role
    )

    target_column, target_value = _resolve_target(
        question=question,
        role=role,
    )

    if (
        target_column is None
        or target_value is None
    ):
        return {
            "question": question,
            "dataset_name": (
                schema.dataset_name
            ),
            "decision_type": (
                "investment_or_expansion"
            ),
            "target_resolved": False,
            "target": None,
            "structured_evidence": None,
            "forecast_evidence": None,
            "rag_evidence": None,
            "scenario_readiness": (
                _scenario_readiness(
                    question
                )
            ),
            "risks": [
                (
                    "Decision target could not be resolved to one permitted "
                    "business entity."
                )
            ],
            "missing_information": [
                (
                    "Specify one target such as a region, country, product, "
                    "segment, or other permitted category."
                )
            ],
            "recommendation_ready": False,
        }

    measures = _preferred_measures(
        measures=list(
            schema.measures
        ),
        dataset_name=(
            schema.dataset_name
        ),
    )

    measure_packages: dict[
        str,
        Any
    ] = {}

    for measure in measures:
        measure_packages[
            measure
        ] = _measure_evidence(
            role=role,
            measure=measure,
            group_by=target_column,
            group_value=target_value,
        )

    structured = {
        "target_column": (
            target_column
        ),
        "target_value": (
            target_value
        ),
        "measures": (
            measure_packages
        ),
    }

    forecast = _forecast_evidence(
        role=role,
        measures=measures,
    )

    rag = _rag_evidence(
        question=question,
        role=role,
        dataset_name=(
            schema.dataset_name
        ),
        target_column=(
            target_column
        ),
        target_value=(
            target_value
        ),
    )

    scenario = _scenario_readiness(
        question
    )

    risks = _structured_risks(
        structured
    )

    if not forecast.get(
        "available"
    ):
        risks.append(
            "Forecast evidence is unavailable."
        )

    else:
        confidence = (
            forecast.get(
                "diagnostics",
                {}
            ).get(
                "confidence"
            )
        )

        if confidence == "low":
            risks.append(
                "Forecast confidence is low."
            )

        for warning in (
            forecast.get(
                "diagnostics",
                {}
            ).get(
                "warnings",
                []
            )
            or []
        ):
            risks.append(
                f"Forecast warning: {warning}"
            )

    if not rag.get(
        "available"
    ):
        risks.append(
            "Authorized RAG evidence is unavailable."
        )

    elif rag.get(
        "count",
        0,
    ) == 0:
        risks.append(
            "No relevant authorized document evidence was retrieved."
        )

    risks.append(
        "Quantified investment ROI is not supported without a "
        "validated investment-response model."
    )

    missing_information = list(
        scenario[
            "missing_inputs"
        ]
    )

    return {
        "question": question,
        "dataset_name": (
            schema.dataset_name
        ),
        "decision_type": (
            "investment_or_expansion"
        ),
        "target_resolved": True,
        "target": {
            "column": target_column,
            "value": target_value,
        },
        "structured_evidence": (
            structured
        ),
        "forecast_evidence": (
            forecast
        ),
        "rag_evidence": rag,
        "scenario_readiness": (
            scenario
        ),
        "risks": risks,
        "missing_information": (
            missing_information
        ),
        "evidence_quality": {
            "structured_available": any(
                item.get(
                    "available"
                )
                for item
                in measure_packages.values()
            ),
            "forecast_available": (
                bool(
                    forecast.get(
                        "available"
                    )
                )
            ),
            "forecast_confidence": (
                forecast.get(
                    "diagnostics",
                    {}
                ).get(
                    "confidence"
                )
                if forecast.get(
                    "available"
                )
                else None
            ),
            "rag_available": (
                bool(
                    rag.get(
                        "available"
                    )
                )
            ),
            "rag_document_count": (
                int(
                    rag.get(
                        "count",
                        0,
                    )
                )
            ),
            "quantified_roi_model_available": False,
        },
        # Stage 15.1 intentionally does not generate a recommendation.
        "recommendation_ready": False,
        "recommendation_status": (
            "Evidence package ready for Stage 15.2 assessment, "
            "but quantified ROI remains unsupported."
        ),
    }

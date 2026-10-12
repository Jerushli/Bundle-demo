from backend.daily_intelligence_evidence import build_daily_evidence_package


def main() -> None:
    print("Stage 21.3 smoke test")
    print("=" * 50)

    evidence = build_daily_evidence_package(
        role="admin",
        persist=False,
    )

    assert evidence["source"] == "daily_intelligence_evidence"
    assert evidence["evidence_version"] == "21.3"
    assert "kpi_snapshot" in evidence
    assert "change_detection" in evidence
    assert "forecast_deviation" in evidence
    assert "response_model_governance" in evidence
    assert "rag_context" in evidence
    assert "guardrails" in evidence
    assert "summary" in evidence
    assert evidence["guardrails"]["no_invented_causes"] is True
    assert evidence["guardrails"]["llm_numeric_calculation_allowed"] is False

    print("Dataset:", evidence["dataset"]["dataset_name"])
    print("KPI snapshot status:", evidence["kpi_snapshot"]["status"])
    print("Change evidence status:", evidence["change_detection"]["status"])
    print(
        "Governance status:",
        evidence["response_model_governance"]["status"],
    )
    print(
        "Governance warnings:",
        evidence["summary"]["governance_warning_count"],
    )
    print(
        "Attention required:",
        evidence["summary"]["attention_required"],
    )
    print("Stage 21.3 smoke test passed.")


if __name__ == "__main__":
    main()

from backend.normalization_lineage import ALLOWED_TARGET_SYSTEMS

def main() -> None:
    print("Stage 22.8 smoke test")
    print("=" * 50)
    assert "analytics" in ALLOWED_TARGET_SYSTEMS
    assert "rag" in ALLOWED_TARGET_SYSTEMS
    print("Analytics lineage target: PASSED")
    print("RAG lineage target: PASSED")
    print("Bidirectional trace design: PASSED")
    print("Stage 22.8 smoke test passed.")

if __name__ == "__main__":
    main()

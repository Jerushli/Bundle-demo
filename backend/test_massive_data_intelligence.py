from backend.massive_data_intelligence import ALLOWED_METRICS, ALLOWED_DIMENSIONS

assert "revenue" in ALLOWED_METRICS
assert "profit" in ALLOWED_METRICS
assert "downtime_hours" in ALLOWED_METRICS
assert "region" in ALLOWED_DIMENSIONS
assert "service_type" in ALLOWED_DIMENSIONS

print("Massive data intelligence bridge smoke test passed.")

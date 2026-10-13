
from backend.streaming_company_loader import _safe_name, _pg_type, _convert

assert _safe_name("Veyora Massive") == "veyora_massive"
assert _pg_type("numeric") == "DOUBLE PRECISION"
assert _pg_type("date") == "DATE"
assert _convert("197798.05", "numeric") == 197798.05
assert str(_convert("2025-09-16", "date")) == "2025-09-16"
assert _convert("Yes", "boolean") is True

print("Massive data streaming loader smoke test passed.")

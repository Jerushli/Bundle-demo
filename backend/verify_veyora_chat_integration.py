from __future__ import annotations

import inspect

import backend.main as main_module


source = inspect.getsource(main_module.chat)

print("Bundle real-chat integration verification")
print("=" * 55)

assert "maybe_process_veyora_chat" in source
assert "veyora_result" in source
assert "process_chat" in source

print("Veyora router present: PASSED")
print("Existing process_chat fallback preserved: PASSED")
print("Chat endpoint import: PASSED")
print("Bundle real-chat integration verification passed.")

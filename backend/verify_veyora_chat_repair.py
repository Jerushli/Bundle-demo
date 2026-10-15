from __future__ import annotations

import inspect

import backend.main as main_module


source = inspect.getsource(
    main_module.chat
)

print(
    "Bundle repaired chat integration verification"
)
print("=" * 58)

assert (
    "veyora_result = maybe_process_veyora_chat"
    in source
)

assert (
    "if veyora_result is not None:"
    in source
)

assert (
    'elif chat_mode == "legacy":'
    in source
)

assert (
    "process_chat("
    in source
)

assert (
    "process_dataset_chat("
    in source
)

assert (
    source.find(
        "veyora_result = maybe_process_veyora_chat"
    )
    < source.find(
        'elif chat_mode == "legacy":'
    )
)

print("Veyora dispatch initialized: PASSED")
print("Legacy chat branch preserved: PASSED")
print("Dataset chat branch preserved: PASSED")
print("UnboundLocalError path removed: PASSED")
print(
    "Repaired chat integration verification passed."
)

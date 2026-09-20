import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "integration" / "opik_support.py"
_SPEC = importlib.util.spec_from_file_location("opik_support", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
opik_support = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(opik_support)


def test_find_key_values_reads_nested_json_string() -> None:
    payload = {
        "input": {
            "value": (
                '{"model":"qwen3.8-27b-exl3-3.5bpw-wm","top_k":20,'
                '"min_p":0.0,"chat_template_kwargs":{"enable_thinking":false}}'
            )
        }
    }

    assert "qwen3.8-27b-exl3-3.5bpw-wm" in opik_support.find_key_values(payload, "model")
    assert 20 in opik_support.find_key_values(payload, "top_k")
    assert 0.0 in opik_support.find_key_values(payload, "min_p")
    assert False in opik_support.find_key_values(payload, "enable_thinking")

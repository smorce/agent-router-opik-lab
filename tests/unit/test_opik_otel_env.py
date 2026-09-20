import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts" / "lib" / "opik-otel-env.sh"
START_SCRIPT = REPO_ROOT / "scripts" / "start-agent-router.sh"


def _run_helper(expression: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f'source "{HELPER}" && {expression}'],
        check=False,
        capture_output=True,
        text=True,
    )


def test_opik_enabled_true_exports_otlp() -> None:
    result = _run_helper('otel_traces_exporter_from_opik_enabled true')
    assert result.returncode == 0
    assert result.stdout.strip() == "otlp"


def test_opik_enabled_false_exports_none() -> None:
    result = _run_helper('otel_traces_exporter_from_opik_enabled false')
    assert result.returncode == 0
    assert result.stdout.strip() == "none"


def test_opik_base_url_builds_otlp_traces_endpoint() -> None:
    result = _run_helper(
        'otel_traces_endpoint_from_opik_base_url "http://127.0.0.1:5181/"'
    )
    assert result.returncode == 0
    assert (
        result.stdout.strip()
        == "http://127.0.0.1:5181/api/v1/private/otel/v1/traces"
    )


def test_opik_enabled_invalid_is_rejected() -> None:
    result = _run_helper("otel_traces_exporter_from_opik_enabled maybe")
    assert result.returncode != 0
    assert "OPIK_ENABLED must be true or false" in result.stderr


def test_start_agent_router_uses_opik_enabled_and_header_mapping() -> None:
    start_text = START_SCRIPT.read_text(encoding="utf-8")
    helper_text = HELPER.read_text(encoding="utf-8")
    assert "otel_traces_exporter_from_opik_enabled" in start_text
    assert "otel_traces_endpoint_from_opik_base_url" in start_text
    assert "OTEL_AIGW_SPAN_REQUEST_HEADER_ATTRIBUTES" in start_text
    assert "default_span_request_header_attributes" in start_text
    assert "x-session-id:session.id" in helper_text
    assert "x-request-id:request.id" in helper_text

"""The framework-neutral agent tools, against the conformance mock.

Every failure must come back as data: a raised exception would end the agent's loop.
"""
from __future__ import annotations

import json
import os
import urllib.request

import httpx
import pytest

from rendobar import Rendobar
from rendobar.agents import tool_definitions

MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")


@pytest.fixture(autouse=True)
def _fresh() -> None:
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset", method="POST"), timeout=5)


def tools(client: Rendobar) -> dict:
    return {d.name: d for d in tool_definitions(client)}


def test_the_four_tools_match_the_mcp_verbs() -> None:
    assert sorted(tools(Rendobar("k", base_url=MOCK))) == ["get_job", "list_job_types", "probe_media", "run_job"]


def test_list_job_types_reads_the_live_registry() -> None:
    result = tools(Rendobar("k", base_url=MOCK))["list_job_types"].run()
    assert result["job_types"] and {"type", "summary", "use_cases"} <= set(result["job_types"][0])


def test_run_job_without_wait_returns_the_created_job() -> None:
    result = tools(Rendobar("k", base_url=MOCK))["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"}, wait=False)
    assert result["id"].startswith("job_")


def test_a_missing_job_is_data_not_an_exception() -> None:
    result = tools(Rendobar("k", base_url=MOCK))["get_job"].run(id="job_404")
    error = result["error"]
    assert error["code"] == "NOT_FOUND" and error["request_id"].startswith("req_")
    # The code and request id are fields of their own, never repeated inside the message.
    assert "NOT_FOUND" not in error["message"] and error["request_id"] not in error["message"]


def test_get_job_and_run_job_report_an_api_error_the_same_way() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "FORBIDDEN", "message": "This key cannot read jobs"}}
        return httpx.Response(403, json=body, headers={"x-request-id": "req_same"})

    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, httpx.MockTransport(refuse))
    expected = {"error": {"code": "FORBIDDEN", "message": "This key cannot read jobs", "request_id": "req_same"}}
    assert tools(client)["get_job"].run(id="job_x") == expected
    assert tools(client)["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"}) == expected


def test_a_missing_key_is_not_offered_as_a_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDOBAR_API_KEY", raising=False)
    result = tools(Rendobar(base_url=MOCK))["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"})
    assert result["error"]["code"] == "MISSING_API_KEY" and "idempotency_key" not in result


class _Down(httpx.HTTPTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)


def tap(client: Rendobar, transport: httpx.BaseTransport) -> None:
    client._core._client_wrapper.httpx_client.httpx_client._transport = transport  # noqa: SLF001 (test-only tap)


def test_a_dropped_connection_is_data_not_an_exception() -> None:
    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, _Down())
    result = tools(client)["get_job"].run(id="job_x")
    assert result["error"]["code"] == "CONNECTION_ERROR" and result["error"]["message"].endswith("The call can be retried.")


class _SubmitOnly(httpx.HTTPTransport):
    """Submits reach the mock; every poll afterwards fails to connect."""

    def __init__(self) -> None:
        super().__init__()
        self.bodies: list = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/jobs":
            self.bodies.append(json.loads(request.content))
            return super().handle_request(request)
        raise httpx.ConnectError("connection refused", request=request)


def test_run_job_waits_and_returns_the_output() -> None:
    result = tools(Rendobar("k", base_url=MOCK))["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"})
    assert result["status"] == "complete" and result["url"].startswith("https://") and "error" not in result


def test_a_failure_after_the_job_exists_points_to_get_job_not_a_retry() -> None:
    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, _SubmitOnly())
    result = tools(client)["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"})
    assert result["id"].startswith("job_") and result["status"] == "waiting"
    assert result["error"]["code"] == "CONNECTION_ERROR"
    assert result["hint"] == "Call get_job with this id."
    assert "retried" not in json.dumps(result)


def test_probe_media_after_the_job_exists_points_to_get_job() -> None:
    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, _SubmitOnly())
    result = tools(client)["probe_media"].run(url="https://x/a.mp4")
    assert result["id"].startswith("job_") and result["hint"] == "Call get_job with this id."
    assert "retried" not in json.dumps(result)


def test_a_failed_submit_may_be_retried_with_the_same_key() -> None:
    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, _Down())
    first = tools(client)["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"})
    assert "id" not in first and first["idempotency_key"].startswith("sdk_")
    assert first["error"]["message"].endswith("The call can be retried with this idempotency_key.")
    recorder = _SubmitOnly()
    retry_client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(retry_client, recorder)
    tools(retry_client)["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"}, wait=False, idempotency_key=first["idempotency_key"])
    assert recorder.bodies[0]["idempotencyKey"] == first["idempotency_key"]


def test_a_refused_submit_is_not_offered_as_a_retry() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "VALIDATION_ERROR", "message": "params.command is required"}})

    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, httpx.MockTransport(refuse))
    result = tools(client)["run_job"].run(type="ffprobe", params={})
    assert result == {"error": {"code": "VALIDATION_ERROR", "message": "params.command is required"}}


def test_a_rate_limited_submit_may_be_retried_with_its_key() -> None:
    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": "RATE_LIMITED", "message": "Too many requests"}})

    client = Rendobar("k", base_url=MOCK, max_retries=0)
    tap(client, httpx.MockTransport(limited))
    result = tools(client)["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"})
    assert result["idempotency_key"].startswith("sdk_") and result["error"]["code"] == "RATE_LIMITED"

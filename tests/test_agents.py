"""The framework-neutral agent tools, against the conformance mock.

Every failure must come back as data: a raised exception would end the agent's loop.
"""
from __future__ import annotations

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
    assert result["error"]["code"] == "NOT_FOUND" and result["error"]["request_id"].startswith("req_")


class _Down(httpx.HTTPTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)


def test_a_dropped_connection_is_data_not_an_exception() -> None:
    client = Rendobar("k", base_url=MOCK, max_retries=0)
    client._core._client_wrapper.httpx_client.httpx_client._transport = _Down()  # noqa: SLF001 (test-only tap)
    result = tools(client)["get_job"].run(id="job_x")
    assert result["error"]["code"] == "REQUEST_FAILED" and result["error"]["message"].endswith("The call can be retried.")

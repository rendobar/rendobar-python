"""The shared SDK conformance scenarios (rendobar/openapi conformance/SCENARIOS.md).

Runs against the conformance mock (`RENDOBAR_MOCK`, default http://127.0.0.1:4100),
the same server every Rendobar SDK is tested against. CI starts it from the
pinned conformance image and fails unless every scenario id passes.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import warnings

import httpx
import pytest

from rendobar import NotFoundError, InternalServerError, Rendobar, RendobarError, UnknownJob, __version__

MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")


def reset(query: str = "") -> None:
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset{query}", method="POST"), timeout=5)


@pytest.fixture(autouse=True)
def _fresh() -> None:
    reset()


@pytest.fixture
def rb() -> Rendobar:
    return Rendobar("rb_conformance", base_url=MOCK)


class Recorder(httpx.HTTPTransport):
    """Records what the SDK sends; the network itself is real."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return super().handle_request(request)


def recording(client: Rendobar) -> Recorder:
    recorder = Recorder()
    client._core._client_wrapper.httpx_client.httpx_client._transport = recorder  # noqa: SLF001 (test-only tap)
    return recorder


def test_c01_public_endpoint_without_a_key() -> None:
    assert len(Rendobar(base_url=MOCK, api_key=None).jobs.types()) > 0


def test_c02_get_unwraps_the_job(rb: Rendobar) -> None:
    job = rb.jobs.get("job_x")
    assert job.id == "job_x"


def test_c03_create_returns_the_job_id(rb: Rendobar) -> None:
    assert rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"}).id.startswith("job_")


def test_c04_list_all_pages_through_every_job(rb: Rendobar) -> None:
    assert sum(1 for _ in rb.jobs.list_all(page_size=50)) == 120


def test_c05_typed_not_found(rb: Rendobar) -> None:
    with pytest.raises(NotFoundError) as info:
        rb.jobs.get("job_404")
    assert info.value.code == "NOT_FOUND" and info.value.status_code == 404


def test_c06_retries_429_after_retry_after(rb: Rendobar) -> None:
    started = time.monotonic()
    assert rb.jobs.get("job_flaky").id == "job_flaky"
    assert 0.9 <= time.monotonic() - started < 3


def test_c07_retries_503_then_raises(rb: Rendobar) -> None:
    with pytest.raises(InternalServerError) as info:
        rb.jobs.get("job_503")
    assert info.value.status_code == 503


def test_c08_timeout() -> None:
    fast = Rendobar("k", base_url=MOCK, timeout=2.0, max_retries=0)
    started = time.monotonic()
    with pytest.raises(Exception):
        fast.jobs.get("job_slow")
    assert 1.8 <= time.monotonic() - started < 4


def test_c09_unknown_status_does_not_raise(rb: Rendobar) -> None:
    job = rb.jobs.get("job_future")
    assert job.status == "paused"
    assert isinstance(job, UnknownJob) and job.raw["brandNewField"] == {"added": "later"}


def test_c10_download_returns_the_bytes(rb: Rendobar) -> None:
    assert len(rb.jobs.download("job_x")) == 1024


def test_c11_every_request_names_this_sdk(rb: Rendobar) -> None:
    recorder = recording(rb)
    rb.jobs.get("job_x")
    rb.jobs.types()
    assert recorder.requests
    for request in recorder.requests:
        assert request.headers["X-Rendobar-Client"].startswith(f"python/{__version__} (python/")


def test_c12_error_carries_the_request_id(rb: Rendobar) -> None:
    with pytest.raises(RendobarError) as info:
        rb.jobs.get("job_404")
    assert (info.value.request_id or "").startswith("req_")


def test_c13_retried_submit_creates_one_job(rb: Rendobar) -> None:
    reset("?lose_submit=1")
    recorder = recording(rb)
    rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"})
    keys = [json.loads(r.content)["idempotencyKey"] for r in recorder.requests if r.url.path == "/jobs"]
    created = json.load(urllib.request.urlopen(f"{MOCK}/__created", timeout=5))["data"]["count"]
    assert len(keys) == 2 and keys[0] == keys[1] and keys[0].startswith("sdk_")
    assert created == 1


def test_c14_deprecated_endpoint_reported_once() -> None:
    notices = []
    client = Rendobar("k", base_url=MOCK, on_deprecation=notices.append)
    client.jobs.get("job_x")  # current endpoint: silent
    assert notices == []
    # No public Python method maps to a deprecated route; call one through the
    # same plumbing every method uses.
    raw = client._core.billing.with_raw_response  # noqa: SLF001
    for _ in range(2):
        client._call("POST", "/billing/checkout/pro", raw.create_pro_checkout)  # noqa: SLF001
    assert len(notices) == 1 and notices[0].path == "/billing/checkout/pro"
    assert notices[0].deprecated_at.date().isoformat() == "2026-10-17"


def test_c15_reads_the_key_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDOBAR_API_KEY", "rb_from_env")
    client = Rendobar(base_url=MOCK)
    recorder = recording(client)
    client.jobs.get("job_x")
    assert recorder.requests[0].headers["Authorization"] == "Bearer rb_from_env"


def test_default_deprecation_warning_is_a_python_warning() -> None:
    client = Rendobar("k", base_url=MOCK)
    raw = client._core.billing.with_raw_response  # noqa: SLF001
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client._call("POST", "/billing/checkout/pro", raw.create_pro_checkout)  # noqa: SLF001
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)

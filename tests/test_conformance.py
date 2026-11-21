"""The shared SDK conformance scenarios (rendobar/openapi conformance/SCENARIOS.md).

Runs against the conformance mock (`RENDOBAR_MOCK`, default http://127.0.0.1:4100),
the same server every Rendobar SDK is tested against. CI starts it from the
pinned conformance image and fails unless every scenario id passes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import warnings

import httpx
import pytest

from rendobar import (
    APITimeoutError,
    AuthenticationError,
    ConflictError,
    InternalServerError,
    InvalidArgumentError,
    JobCancelled,
    JobCreated,
    JobFailed,
    JobFailedError,
    JobReplayed,
    NotFoundError,
    Rendobar,
    RendobarDeprecationWarning,
    RendobarError,
    UnknownJob,
    WaitTimeoutError,
    __version__,
)

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
    recorder = recording(rb)
    with pytest.raises(InternalServerError) as info:
        rb.jobs.get("job_503")
    assert info.value.status_code == 503
    assert len(recorder.requests) == 3  # the first try and two retries


def test_c08_timeout() -> None:
    fast = Rendobar("rb_k", base_url=MOCK, timeout=2.0, max_retries=0)
    started = time.monotonic()
    with pytest.raises(APITimeoutError) as info:
        fast.jobs.get("job_slow")
    assert info.value.code == "TIMEOUT" and info.value.status_code is None
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
    client = Rendobar("rb_k", base_url=MOCK, on_deprecation=notices.append)
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


def test_c16_run_returns_the_complete_job_with_its_file(rb: Rendobar) -> None:
    seen: list = []
    job = rb.jobs.run("ffprobe", {"command": "https://x/a.mp4"}, interval=0.05, on_progress=lambda j: seen.append(j.status))
    assert seen == ["running", "complete"]
    assert job.status == "complete" and job.output.file is not None and job.output.file.url.startswith("https://")


def test_c17_wait_raises_the_failed_jobs_error_code(rb: Rendobar) -> None:
    with pytest.raises(JobFailedError) as info:
        rb.jobs.wait("job_failed", throw_on_failure=True)
    assert isinstance(info.value, RendobarError)
    assert isinstance(info.value.job, JobFailed) and info.value.code == info.value.job.error.code and info.value.code
    assert info.value.job_id == "job_failed" and info.value.status == "failed"


def test_c17_without_raising_returns_the_failed_job(rb: Rendobar) -> None:
    assert rb.jobs.wait("job_failed").status == "failed"


def test_c18_conflict_is_not_retried(rb: Rendobar) -> None:
    recorder = recording(rb)
    with pytest.raises(ConflictError) as info:
        rb.jobs.get("job_409")
    assert info.value.status_code == 409 and info.value.code == "CONFLICT"
    assert len(recorder.requests) == 1


def test_default_deprecation_warning_is_a_python_warning() -> None:
    client = Rendobar("rb_k", base_url=MOCK)
    raw = client._core.billing.with_raw_response  # noqa: SLF001
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client._call("POST", "/billing/checkout/pro", raw.create_pro_checkout)  # noqa: SLF001
    assert [w.category for w in caught if issubclass(w.category, FutureWarning)] == [RendobarDeprecationWarning]
    assert issubclass(RendobarDeprecationWarning, FutureWarning)


def test_deprecation_warning_is_shown_under_default_filters() -> None:
    script = (
        "import sys; from rendobar import Rendobar; c = Rendobar('rb_k', base_url=sys.argv[1]); "
        "c._call('POST', '/billing/checkout/pro', c._core.billing.with_raw_response.create_pro_checkout)"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONWARNINGS"}
    out = subprocess.run([sys.executable, "-c", script, MOCK], capture_output=True, text=True, env=env, timeout=30, check=True)
    assert "RendobarDeprecationWarning" in out.stderr and "/billing/checkout/pro" in out.stderr


def test_close_and_context_manager() -> None:
    with Rendobar("rb_k", base_url=MOCK) as client:
        assert client.jobs.get("job_x").id == "job_x"
    assert client._core._client_wrapper.httpx_client.httpx_client.is_closed  # noqa: SLF001


# ── C19-C39: the cross-SDK behaviour standard ─────────────────────────
# Scenarios that need mock features newer than rendobar/openapi main skip
# until the mock serves them (it answers GET /__requests).

@pytest.fixture
def parity_mock() -> None:
    try:
        urllib.request.urlopen(f"{MOCK}/__requests", timeout=5)
    except Exception:  # noqa: BLE001 (an older mock answers 404)
        pytest.skip("needs the parity mock (GET /__requests)")


def requests_seen() -> list:
    return json.load(urllib.request.urlopen(f"{MOCK}/__requests", timeout=5))["data"]


def created_count() -> int:
    return json.load(urllib.request.urlopen(f"{MOCK}/__created", timeout=5))["data"]["count"]


def test_c19_no_key_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDOBAR_API_KEY", raising=False)
    client = Rendobar(base_url=MOCK)
    recorder = recording(client)
    with pytest.raises(AuthenticationError) as info:
        client.jobs.get("job_x")
    message = str(info.value)
    assert info.value.code == "MISSING_API_KEY" and "RENDOBAR_API_KEY" in message and "api_key" in message
    assert recorder.requests == []


def test_c20_a_key_without_rb_fails_locally() -> None:
    client = Rendobar("sk_x", base_url=MOCK)
    recorder = recording(client)
    with pytest.raises(AuthenticationError) as info:
        client.jobs.get("job_x")
    assert info.value.code == "INVALID_API_KEY" and recorder.requests == []


def test_c21_a_trailing_slash_never_doubles_the_path() -> None:
    client = Rendobar("rb_conformance", base_url=f"{MOCK}/")
    recorder = recording(client)
    client.jobs.get("job_x")
    assert [r.url.raw_path for r in recorder.requests] == [b"/jobs/job_x"]


def test_c22_a_cut_off_submit_carries_the_key_and_resubmits_to_the_same_job(parity_mock: None) -> None:
    reset("?stall_submit=1")
    client = Rendobar("rb_conformance", base_url=MOCK, timeout=2.0)
    with pytest.raises(APITimeoutError) as info:
        client.jobs.create("ffprobe", {"command": "https://x/a.mp4"})
    key = info.value.idempotency_key
    assert key is not None and key.startswith("sdk_")
    again = client.jobs.create("ffprobe", {"command": "https://x/a.mp4"}, idempotency_key=key)
    assert isinstance(again, JobReplayed) and created_count() == 1


def test_c23_same_key_different_params_is_a_conflict_after_one_request(parity_mock: None, rb: Rendobar) -> None:
    rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"}, idempotency_key="order-23")
    before = len(requests_seen())
    with pytest.raises(ConflictError) as info:
        rb.jobs.create("ffprobe", {"command": "https://x/b.mp4"}, idempotency_key="order-23")
    assert info.value.code == "CONFLICT" and len(requests_seen()) == before + 1


def test_c24_same_key_same_params_replays_the_job(rb: Rendobar) -> None:
    first = rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"}, idempotency_key="order-24")
    second = rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"}, idempotency_key="order-24")
    assert isinstance(first, JobCreated) and isinstance(second, JobReplayed) and second.id == first.id


def test_c25_a_503_retry_after_is_honoured(parity_mock: None, rb: Rendobar) -> None:
    started = time.monotonic()
    assert rb.jobs.get("job_503_ra").id == "job_503_ra"
    assert 0.9 <= time.monotonic() - started < 3


def test_c26_a_long_retry_after_is_raised_after_one_request(parity_mock: None, rb: Rendobar) -> None:
    with pytest.raises(RendobarError) as info:
        rb.jobs.get("job_ra_long")
    assert info.value.retry_after == 3600 and len(requests_seen()) == 1


def test_c27_an_http_date_retry_after_is_honoured(parity_mock: None, rb: Rendobar) -> None:
    started = time.monotonic()
    assert rb.jobs.get("job_ra_date").id == "job_ra_date"
    assert 0.5 <= time.monotonic() - started < 4 and len(requests_seen()) == 2


def test_c28_a_501_is_not_retried(parity_mock: None, rb: Rendobar) -> None:
    with pytest.raises(RendobarError) as info:
        rb.jobs.get("job_501")
    assert info.value.status_code == 501 and len(requests_seen()) == 1


def test_c29_list_all_follows_the_rows_returned(parity_mock: None, rb: Rendobar) -> None:
    assert len(list(rb.jobs.list_all(page_size=500))) == 120
    queries = [r["query"] for r in requests_seen() if r["path"] == "/jobs"]
    assert len(queries) == 2 and "offset=0" in queries[0] and "offset=100" in queries[1]


def test_c30_a_phantom_total_does_not_loop(parity_mock: None, rb: Rendobar) -> None:
    reset("?phantom_total=1")
    assert len(list(rb.jobs.list_all())) == 60


def test_c31_a_bad_page_window_fails_locally(rb: Rendobar) -> None:
    recorder = recording(rb)
    with pytest.raises(InvalidArgumentError):
        rb.jobs.list(limit=0)
    with pytest.raises(InvalidArgumentError):
        rb.jobs.list(offset=-1)
    assert recorder.requests == []


@pytest.mark.parametrize("job_id", ["", "a/b", ".."])
def test_c32_an_unsafe_id_fails_locally(rb: Rendobar, job_id: str) -> None:
    recorder = recording(rb)
    with pytest.raises(InvalidArgumentError):
        rb.jobs.get(job_id)
    assert recorder.requests == []


def test_c33_an_invalid_submit_exposes_its_problems(parity_mock: None, rb: Rendobar) -> None:
    with pytest.raises(RendobarError) as info:
        rb.jobs.create("no_such_type", {})
    problems = info.value.problems
    assert info.value.code == "VALIDATION_ERROR" and problems and problems[0].path == ("type",) and problems[0].message


def test_c34_a_wait_timeout_carries_the_last_job(parity_mock: None, rb: Rendobar) -> None:
    with pytest.raises(WaitTimeoutError) as info:
        rb.jobs.wait("job_stuck", timeout=3, interval=0.5)
    assert info.value.job_id == "job_stuck" and info.value.last_status == "running"
    assert info.value.job.id == "job_stuck" and info.value.job.status == "running"


def test_c35_wait_returns_a_cancelled_job_and_run_raises(parity_mock: None, rb: Rendobar) -> None:
    assert isinstance(rb.jobs.wait("job_cancelled"), JobCancelled)
    reset("?cancel_created=1")
    with pytest.raises(JobFailedError) as info:
        rb.jobs.run("ffprobe", {"command": "https://x/a.mp4"}, interval=0.05)
    assert info.value.code == "JOB_CANCELLED" and isinstance(info.value.job, JobCancelled)


def test_c36_a_timed_out_request_is_sent_once() -> None:
    client = Rendobar("rb_conformance", base_url=MOCK, timeout=2.0)
    recorder = recording(client)
    with pytest.raises(APITimeoutError):
        client.jobs.get("job_slow")
    assert len(recorder.requests) == 1


def test_c37_waiting_on_a_newer_status_times_out_without_crashing(rb: Rendobar) -> None:
    with pytest.raises(WaitTimeoutError) as info:
        rb.jobs.wait("job_future", timeout=3, interval=0.5)
    assert info.value.last_status == "paused" and isinstance(info.value.job, UnknownJob)


def test_c38_the_client_header_names_the_package_version_runtime_and_app() -> None:
    client = Rendobar("rb_conformance", base_url=MOCK, app="conformance")
    recorder = recording(client)
    client.jobs.get("job_x")
    header = recorder.requests[0].headers["X-Rendobar-Client"]
    assert header.startswith(f"python/{__version__} (python/") and header.endswith("; app/conformance)")

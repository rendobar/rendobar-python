"""Pure-logic units shared by the sync and async clients: the wait deadline, the
retry decision, and the unknown-status fallback on every call that returns jobs.

No mock server: the HTTP side is an httpx.MockTransport.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

import httpx
import pytest

from rendobar import (
    APIConnectionError,
    APITimeoutError,
    AsyncRendobar,
    ConflictError,
    JobFailedError,
    Rendobar,
    RendobarError,
    ResponseValidationError,
    UnknownJob,
    WaitTimeoutError,
)
from rendobar._client import WaitClock, WaitPoll, retry_delay, split_run_options
from rendobar._generated.core.api_error import ApiError
from rendobar._generated.core.parse_error import ParsingError


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class Job:
    def __init__(self, status: str, timeout_ms: Optional[int] = None, job_id: str = "job_1") -> None:
        self.id = job_id
        self.status = status
        self.timeout_ms = timeout_ms
        self.error = None


# ── WaitClock ─────────────────────────────────────────────────────────

def test_default_bound_is_five_minutes_from_the_start_even_while_queued() -> None:
    clock = FakeClock()
    wait = WaitClock(None, clock=clock)
    for _ in range(10):
        clock.now += 60
        wait.observe(Job("waiting"))
    assert wait.deadline == 1000 + 300  # queued polls never slide the bound
    assert wait.remaining() < 0


def test_budget_is_adopted_from_the_poll_that_reports_it() -> None:
    clock = FakeClock()
    wait = WaitClock(None, clock=clock)
    clock.now += 250  # the job sat in the queue for 250 s
    wait.observe(Job("running", timeout_ms=600_000))
    assert wait.deadline == 1250 + 600 + 120  # now + budget + grace, not start + budget + grace


def test_budget_adoption_never_shortens_the_default_bound() -> None:
    clock = FakeClock()
    wait = WaitClock(None, clock=clock)
    clock.now += 10
    wait.observe(Job("running", timeout_ms=1))
    assert wait.deadline == 1000 + 300


def test_budget_is_adopted_once() -> None:
    clock = FakeClock()
    wait = WaitClock(None, clock=clock)
    wait.observe(Job("running", timeout_ms=600_000))
    first = wait.deadline
    clock.now += 500
    wait.observe(Job("running", timeout_ms=600_000))
    assert wait.deadline == first


def test_explicit_timeout_ignores_the_budget() -> None:
    clock = FakeClock()
    wait = WaitClock(30, clock=clock)
    wait.observe(Job("running", timeout_ms=600_000))
    assert wait.deadline == 1030 and wait.total() == 30


def test_a_boolean_budget_is_not_a_number() -> None:
    wait = WaitClock(None, clock=FakeClock())
    wait.observe(Job("running", timeout_ms=True))  # type: ignore[arg-type]
    assert not wait.adopted


# ── WaitPoll (the sans-IO half of both wait loops) ────────────────────

def poll(clock: FakeClock, **kw: Any) -> WaitPoll:
    options: Dict[str, Any] = {"timeout": None, "interval": 2.0, "max_interval": 10.0, "throw_on_failure": False}
    options.update(kw)
    return WaitPoll("job_1", clock=clock, **options)


def test_poll_backs_off_to_the_max_interval() -> None:
    clock = FakeClock()
    p = poll(clock)
    pauses = [p.step(Job("running")) for _ in range(6)]
    assert pauses == [2.0, 3.0, 4.5, 6.75, 10.0, 10.0]


def test_poll_never_sleeps_past_the_deadline() -> None:
    clock = FakeClock()
    p = poll(clock, timeout=1.0)
    assert p.step(Job("running")) == 1.0


def test_poll_returns_on_a_terminal_status() -> None:
    p = poll(FakeClock(), throw_on_failure=True)
    assert p.step(Job("complete")) is None


def test_poll_raises_on_failure_when_asked() -> None:
    with pytest.raises(JobFailedError) as info:
        poll(FakeClock(), throw_on_failure=True).step(Job("cancelled"))
    assert info.value.code == "JOB_CANCELLED"
    assert poll(FakeClock()).step(Job("failed")) is None


def test_poll_times_out_with_the_last_status() -> None:
    clock = FakeClock()
    p = poll(clock)
    clock.now += 301
    with pytest.raises(WaitTimeoutError) as info:
        p.step(Job("waiting"))
    assert info.value.last_status == "waiting" and isinstance(info.value, RendobarError)
    assert info.value.code == "WAIT_TIMEOUT"


def test_an_unknown_status_is_not_terminal() -> None:
    assert poll(FakeClock()).step(UnknownJob({"id": "job_1", "status": "paused"})) == 2.0


def test_split_run_options() -> None:
    create, wait = split_run_options({"label": "a", "timeout": 5, "on_progress": print, "idempotency_key": "k"})
    assert create == {"label": "a", "idempotency_key": "k"} and wait == {"timeout": 5, "on_progress": print}


# ── retry_delay ───────────────────────────────────────────────────────

def api_error(status: int, headers: Optional[Dict[str, str]] = None) -> ApiError:
    return ApiError(status_code=status, headers=headers or {}, body={"error": {"code": "X", "message": "x"}})


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 408, 409, 422])
def test_client_errors_are_never_retried(status: int) -> None:
    assert retry_delay(api_error(status), 0, 5) is None


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_429_and_5xx_are_retried_with_backoff(status: int) -> None:
    assert retry_delay(api_error(status), 0, 2, rand=lambda: 0.5) == 0.5
    assert retry_delay(api_error(status), 1, 2, rand=lambda: 0.5) == 1.0
    assert retry_delay(api_error(status), 2, 2) is None


def test_retry_after_is_honoured() -> None:
    assert retry_delay(api_error(429, {"Retry-After": "3"}), 0, 2) == 3.0
    assert retry_delay(api_error(503, {"retry-after": "0"}), 0, 2) == 0.0


def test_a_retry_after_too_long_to_wait_is_raised_instead() -> None:
    assert retry_delay(api_error(429, {"Retry-After": "3600"}), 0, 2) is None


def test_backoff_is_capped() -> None:
    assert retry_delay(api_error(503), 10, 20, rand=lambda: 0.5) == 8.0


def test_connection_failures_are_retried_but_read_timeouts_are_not() -> None:
    request = httpx.Request("GET", "https://x")
    assert retry_delay(httpx.ConnectError("down", request=request), 0, 2) is not None
    assert retry_delay(httpx.ConnectTimeout("slow", request=request), 0, 2) is not None
    assert retry_delay(httpx.ReadTimeout("slow", request=request), 0, 2) is None
    assert retry_delay(ParsingError(status_code=200, body={}), 0, 2) is None


def test_an_unreadable_5xx_body_is_still_retried() -> None:
    assert retry_delay(ParsingError(status_code=503, headers={}, body="<html>"), 0, 2) is not None


# ── the clients over a MockTransport ──────────────────────────────────

def job(job_id: str, status: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": job_id, "status": status, "orgId": "org_1", "type": "ffprobe", "source": "api", "retryCount": 0,
        "inputs": {}, "params": {}, "outputCategory": "json", "steps": [], "logsAvailable": False,
        "resourcesAvailable": False, "createdAt": 1731000000000, "webUrl": "https://app.rendobar.com/jobs/x",
    }
    out.update(extra)
    return out


Handler = Callable[[httpx.Request], httpx.Response]


def routes(pages: Dict[str, Any]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        if key not in pages:
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": key}})
        status, body = pages[key]
        return httpx.Response(status, json=body, headers={"x-request-id": "req_unit"})
    return handle


def _install(http: Any, handler: Handler) -> None:
    http._transport = httpx.MockTransport(handler)
    http._mounts = {}  # no environment proxy in front of the mock


def sync_client(handler: Handler, **kw: Any) -> Rendobar:
    client = Rendobar("k", base_url="https://api.test", **kw)
    _install(client._core._client_wrapper.httpx_client.httpx_client, handler)  # noqa: SLF001
    return client


def async_client(handler: Handler, **kw: Any) -> AsyncRendobar:
    client = AsyncRendobar("k", base_url="https://api.test", **kw)
    _install(client._core._client_wrapper.httpx_client.httpx_client, handler)  # noqa: SLF001
    return client


MIXED_PAGE = {
    "data": [job("job_1", "running"), job("job_2", "paused", brandNewField=1), job("job_3", "waiting")],
    "meta": {"total": 3, "page": 1, "limit": 50},
}
PAGES = {
    "GET /jobs": (200, MIXED_PAGE),
    "GET /jobs/job_2": (200, {"data": job("job_2", "paused")}),
    "POST /jobs": (201, {"data": {"id": "job_9", "status": "paused"}}),
    "POST /jobs/job_2/cancel": (200, {"data": {"id": "job_2", "status": "paused", "idempotent": "not a bool"}}),
}


def check_page(jobs: List[Any]) -> None:
    assert [j.id for j in jobs] == ["job_1", "job_2", "job_3"]
    assert [type(j).__name__ for j in jobs] == ["Job_Running", "UnknownJob", "Job_Waiting"]
    assert jobs[1].status == "paused" and jobs[1].raw["brandNewField"] == 1


def test_one_unknown_status_in_a_list_page_is_one_unknown_job() -> None:
    rb = sync_client(routes(PAGES))
    page = rb.jobs.list()
    check_page(page.data)
    assert page.meta.total == 3
    check_page(list(rb.jobs.list_all()))


def test_async_one_unknown_status_in_a_list_page_is_one_unknown_job() -> None:
    async def go() -> None:
        async with async_client(routes(PAGES)) as rb:
            check_page((await rb.jobs.list()).data)
            check_page([j async for j in rb.jobs.list_all()])
            assert isinstance(await rb.jobs.get("job_2"), UnknownJob)

    asyncio.run(go())


def test_a_known_status_that_does_not_parse_is_not_hidden() -> None:
    bad = {"data": [job("job_1", "running", steps="not a list")], "meta": {"total": 1, "page": 1, "limit": 50}}
    rb = sync_client(routes({"GET /jobs": (200, bad)}))
    with pytest.raises(ResponseValidationError) as info:
        rb.jobs.list()
    assert isinstance(info.value, RendobarError) and info.value.code == "INVALID_RESPONSE"
    assert info.value.body == bad and info.value.request_id == "req_unit"


def test_create_and_cancel_with_a_new_status_do_not_raise() -> None:
    rb = sync_client(routes(PAGES))
    created = rb.jobs.create("ffprobe", {"command": "x"})
    assert created.id == "job_9" and created.status == "paused"
    cancelled = rb.jobs.cancel("job_2")
    assert cancelled.id == "job_2" and cancelled.status == "paused"


def test_one_job_is_the_single_fallback_for_get_create_and_cancel() -> None:
    from rendobar._client import one_job

    newer = ResponseValidationError("x", status_code=200, body={"data": {"id": "job_2", "status": "paused"}})
    assert isinstance(one_job(newer), UnknownJob)
    no_id = ResponseValidationError("x", status_code=200, body={"data": {"status": "paused"}})
    with pytest.raises(ResponseValidationError):  # not a job, so not hidden behind UnknownJob
        one_job(no_id)
    rb = sync_client(routes({"POST /jobs/job_2/cancel": (200, {"data": {"status": "paused"}})}))
    with pytest.raises(ResponseValidationError):
        rb.jobs.cancel("job_2")


def test_create_with_a_known_status_that_does_not_parse_raises() -> None:
    rb = sync_client(routes({"POST /jobs": (201, {"data": {"status": "waiting"}})}))
    with pytest.raises(ResponseValidationError):
        rb.jobs.create("ffprobe", {"command": "x"})


def test_an_error_with_an_unreadable_body_keeps_its_status() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"nope": True})

    with pytest.raises(ConflictError):
        sync_client(handle).jobs.get("job_1")


def test_409_is_sent_once_and_503_three_times() -> None:
    seen: List[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        code = 409 if request.url.path.endswith("job_409") else 503
        return httpx.Response(code, json={"error": {"code": "X", "message": "x"}}, headers={"Retry-After": "0"})

    rb = sync_client(handle)
    with pytest.raises(ConflictError):
        rb.jobs.get("job_409")
    with pytest.raises(RendobarError):
        rb.jobs.get("job_503")
    assert seen == ["/jobs/job_409"] + ["/jobs/job_503"] * 3


def test_transport_failures_are_rendobar_errors() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(APIConnectionError) as info:
        sync_client(down, max_retries=0).jobs.get("job_1")
    assert not isinstance(info.value, APITimeoutError) and info.value.code == "CONNECTION_ERROR"
    with pytest.raises(APITimeoutError):
        sync_client(slow).jobs.get("job_1")


def test_a_connection_failure_is_retried_then_succeeds() -> None:
    calls: List[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"data": job("job_1", "running")})

    assert sync_client(flaky).jobs.get("job_1").status == "running"
    assert len(calls) == 2


def test_submit_retries_reuse_one_idempotency_key() -> None:
    keys: List[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        keys.append(json.loads(request.content)["idempotencyKey"])
        if len(keys) == 1:
            return httpx.Response(502, json={"error": {"code": "BAD_GATEWAY", "message": "x"}}, headers={"Retry-After": "0"})
        return httpx.Response(201, json={"data": {"id": "job_1", "status": "waiting", "idempotent": True}})

    asyncio.run(async_client(handle).jobs.create("ffprobe", {"command": "x"}))
    assert len(keys) == 2 and keys[0] == keys[1]

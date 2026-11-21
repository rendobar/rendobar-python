"""The Rendobar client.

A thin, hand-written layer over the generated core in `_generated` (Fern, from
the published OpenAPI document). The core supplies models, timeouts and HTTP.
It is built with its own retries off: this layer owns them, so only 429, 5xx
and connection failures are retried (never a 409 or 408). It adds what a spec
cannot say:

- the same method names as `@rendobar/sdk` (`jobs.create`, `jobs.run`, ...),
- responses unwrapped from the `{data}` envelope,
- one idempotency key per `jobs.create()` call, so a retried submit cannot
  create a second job,
- `jobs.wait()` / `jobs.run()`, `jobs.list_all()`,
- `RENDOBAR_API_KEY` from the environment, the `X-Rendobar-Client` header,
- `Deprecation` notices, and a job whose status is newer than this SDK
  (`UnknownJob`, from any call that returns jobs),
- one error hierarchy (`RendobarError`) for API errors, transport failures and
  responses this version cannot read.

Everything that is not I/O lives here as plain helpers (`retry_delay`,
`WaitPoll`, `one_job`, `job_page`, ...) that `_async_client` reuses, so the sync
and async clients behave identically.

Behaviour is held to the shared conformance scenarios (tests/test_conformance.py).
"""
from __future__ import annotations

import datetime as _dt
import os
import platform
import random
import re
import secrets
import time
import warnings
from types import TracebackType
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple, Type

import httpx
import pydantic

from ._errors import JobFailedError, ResponseValidationError, WaitTimeoutError, normalize, parse_retry_after, to_public
from ._generated.client import GeneratedClient
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError as _GeneratedParsingError
from ._generated.core.pydantic_utilities import parse_obj_as
from ._generated.jobs.types.list_jobs_response_meta import ListJobsResponseMeta
from ._generated.types.job import Job as _Job
from ._generated.types.submit_any_job import SubmitAnyJob
from ._version import __version__

DEFAULT_BASE_URL = "https://api.rendobar.com"
TERMINAL_STATUSES = frozenset({"complete", "failed", "cancelled"})
KNOWN_STATUSES = frozenset({"waiting", "dispatched", "running", "complete", "failed", "cancelled"})
_DEFAULT_WAIT_TIMEOUT = 300.0  # seconds, until the job reports its own budget
_WAIT_GRACE = 120.0  # headroom past the job's budget for upload and callback
_APP_NAME = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")
_BACKOFF_BASE = 0.5  # seconds before the first retry with no Retry-After
_BACKOFF_CAP = 8.0
_MAX_RETRY_AFTER = 60.0  # a longer Retry-After is raised as a RateLimitError for the caller to schedule

# What a call through the core can fail with. Everything else is a bug and propagates as is.
_CORE_FAILURES: Tuple[Type[BaseException], ...] = (_GeneratedApiError, _GeneratedParsingError, httpx.TransportError)


class RendobarDeprecationWarning(FutureWarning):
    """Emitted once per deprecated endpoint when no `on_deprecation` handler is set.

    A FutureWarning, so Python shows it by default: the code calling the
    endpoint is yours, not a library's, and it stops working at the next major.
    """


class DeprecationNotice:
    """An endpoint the API marked deprecated (RFC 9745 `Deprecation` header)."""

    def __init__(self, method: str, path: str, deprecated_at: _dt.datetime) -> None:
        self.method = method
        self.path = path
        self.deprecated_at = deprecated_at

    def __repr__(self) -> str:
        return f"DeprecationNotice({self.method} {self.path}, since {self.deprecated_at.date()})"


class UnknownJob:
    """A job whose status this SDK version does not know yet.

    Returned instead of raising, so code written today keeps working when the
    API adds a status. `raw` holds the job as the API sent it.
    """

    def __init__(self, raw: Mapping[str, Any]) -> None:
        self.raw = dict(raw)
        self.id: str = str(raw.get("id", ""))
        self.status: str = str(raw.get("status", ""))
        self.type: Optional[str] = raw.get("type")

    def __repr__(self) -> str:
        return f"UnknownJob(id={self.id!r}, status={self.status!r})"


class Page:
    """One page of a list call: `data` plus `meta` (`total`, `page`, `limit`)."""

    def __init__(self, data: List[Any], meta: Any) -> None:
        self.data = data
        self.meta = meta

    def __iter__(self) -> Iterator[Any]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


def generate_idempotency_key() -> str:
    """`sdk_` plus 32 hex characters: unique per call, not secret."""
    return f"sdk_{secrets.token_hex(16)}"


def _client_header(app: Optional[str]) -> str:
    runtime = f"python/{platform.python_version()}"
    extras = [runtime] + ([f"app/{app}"] if app else [])
    return f"python/{__version__} ({'; '.join(extras)})"


def _parse_deprecation(value: Optional[str]) -> Optional[_dt.datetime]:
    """`@1784851200` -> its datetime, or None for anything else, including a value no datetime can hold."""
    match = re.fullmatch(r"@(-?\d+)", (value or "").strip())
    if not match:
        return None
    try:
        return _dt.datetime.fromtimestamp(int(match.group(1)), tz=_dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


_ID_SEGMENT = re.compile(r"/[a-z]+_[A-Za-z0-9_-]+(?=/|$)")


def _route_of(path: str) -> str:
    """`/jobs/job_abc/metrics` -> `/jobs/:id/metrics`: one deprecated endpoint is one notice, whatever ids it gets."""
    return _ID_SEGMENT.sub("/:id", path.split("?", 1)[0])


class _Deprecations:
    """Reports each deprecated route once per client. Shared by the sync and async clients.

    Reporting never changes the call: a handler that raises, or a header no date
    can hold, must not turn a request that succeeded into an exception.
    """

    def __init__(self, handler: Optional[Callable[[DeprecationNotice], None]]) -> None:
        self._handler = handler
        self._seen: set = set()

    def note(self, response: Any, method: str, path: str) -> None:
        since = _parse_deprecation(response.headers.get("deprecation") or response.headers.get("Deprecation"))
        route = _route_of(path)
        key = f"{method} {route}"
        if since is None or key in self._seen:
            return
        self._seen.add(key)
        notice = DeprecationNotice(method, path.split("?", 1)[0], since)
        if self._handler is None:
            warnings.warn(f"[rendobar] {key} is deprecated since {since.date()}. It keeps working until the next major release.", RendobarDeprecationWarning)
            return
        try:
            self._handler(notice)
        except Exception:  # noqa: BLE001 (advisory only, see the class docstring)
            pass


def build_submit(
    type: str,
    params: Optional[Mapping[str, Any]],
    inputs: Optional[Mapping[str, Any]],
    *,
    idempotency_key: Optional[str],
    label: Optional[str],
    destinations: Optional[Sequence[str]],
    callback: Optional[Mapping[str, Any]],
    force_async: Optional[bool],
) -> SubmitAnyJob:
    """The submit body, with a generated idempotency key when the caller gave none."""
    body: Dict[str, Any] = {"type": type, "params": dict(params or {}), "inputs": dict(inputs or {})}
    body["idempotencyKey"] = idempotency_key if idempotency_key is not None else generate_idempotency_key()
    if label is not None:
        body["label"] = label
    if destinations is not None:
        body["destinations"] = list(destinations)
    if callback is not None:
        body["callback"] = dict(callback)
    if force_async is not None:
        body["forceAsync"] = force_async
    return SubmitAnyJob.model_validate(body)  # the untyped variant: valid for every job type


def _is_newer_job(raw: Any) -> bool:
    """A job-shaped body (it has an id) whose status this SDK does not know."""
    return isinstance(raw, Mapping) and isinstance(raw.get("id"), str) and str(raw.get("status", "")) not in KNOWN_STATUSES


def job_from(raw: Any, err: ResponseValidationError) -> Any:
    """One job as the API sent it: the typed model, or `UnknownJob` when its status is newer than this SDK.

    A job with a status this SDK knows that still does not parse is a real
    mismatch, and raises `err` rather than hiding it.
    """
    try:
        return parse_obj_as(_Job, raw)  # type: ignore[arg-type]
    except pydantic.ValidationError:
        if _is_newer_job(raw):
            return UnknownJob(raw)
        raise err from None


def one_job(err: ResponseValidationError) -> Any:
    """Recovers a single-job response (get, create, cancel) the core could not parse."""
    body = err.body
    data = body.get("data") if isinstance(body, Mapping) else None
    if isinstance(data, Mapping) and _is_newer_job(data):
        return UnknownJob(data)
    raise err


def job_page(err: ResponseValidationError) -> "Page":
    """Recovers a list response the core could not parse: each job on its own, so one new status costs one item, not the page."""
    body = err.body
    data = body.get("data") if isinstance(body, Mapping) else None
    if not isinstance(data, list):
        raise err
    try:
        meta = parse_obj_as(ListJobsResponseMeta, body.get("meta"))
    except pydantic.ValidationError:
        raise err from None
    return Page([job_from(item, err) for item in data], meta)


def retry_delay(err: BaseException, attempt: int, max_retries: int, *, rand: Callable[[], float] = random.random) -> Optional[float]:
    """Seconds to wait before retry number `attempt + 1`, or None to raise now.

    Retried: 429 and 5xx (after `Retry-After` when sent, else exponential backoff
    with jitter) and connection failures where the request never reached the API.
    Never retried: any other status (a 409 conflict, a 408), a read timeout (the
    API may still be working on it), and a response this SDK cannot read.
    """
    if attempt >= max_retries:
        return None
    err = normalize(err)
    if isinstance(err, _GeneratedApiError):
        status = err.status_code or 0
        if status != 429 and status < 500:
            return None
        headers = {k.lower(): v for k, v in (err.headers or {}).items()}
        after = parse_retry_after(headers.get("retry-after"))
        if after is not None:
            return after if after <= _MAX_RETRY_AFTER else None
    elif not isinstance(err, (httpx.ConnectError, httpx.ConnectTimeout)):
        return None
    backoff = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
    return backoff * (0.75 + 0.5 * rand())


class WaitClock:
    """The deadline of jobs.wait().

    With an explicit `timeout`, that many seconds from the start of the wait.
    Otherwise five minutes from the start, until the job first reports its
    execution budget (`timeout_ms`); then the later of that bound and the poll's
    time plus the budget plus two minutes' grace. A job stuck in the queue still
    ends the wait at five minutes. `clock` is injectable for tests.
    """

    def __init__(self, timeout: Optional[float], *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.explicit = timeout is not None
        self.started = clock()
        self.deadline = self.started + (timeout if timeout is not None else _DEFAULT_WAIT_TIMEOUT)
        self.adopted = False

    def observe(self, job: Any) -> None:
        budget_ms = getattr(job, "timeout_ms", None)
        if self.explicit or self.adopted or isinstance(budget_ms, bool) or not isinstance(budget_ms, (int, float)):
            return
        self.adopted = True
        self.deadline = max(self.deadline, self._clock() + budget_ms / 1000 + _WAIT_GRACE)

    def remaining(self) -> float:
        return self.deadline - self._clock()

    def total(self) -> float:
        return self.deadline - self.started


class WaitPoll:
    """The decision half of jobs.wait(), with no I/O: the sync and async loops only fetch and sleep.

    `step(job)` returns None when the wait is over (return the job), raises
    `JobFailedError` / `WaitTimeoutError`, or returns the seconds to sleep.
    """

    def __init__(self, job_id: str, *, timeout: Optional[float], interval: float, max_interval: float,
                 throw_on_failure: bool, clock: Callable[[], float] = time.monotonic) -> None:
        self.job_id = job_id
        self.clock = WaitClock(timeout, clock=clock)
        self._delay = interval
        self._max_interval = max_interval
        self._throw = throw_on_failure

    def step(self, job: Any) -> Optional[float]:
        if job.status in TERMINAL_STATUSES:
            if self._throw and job.status != "complete":
                raise JobFailedError(job)
            return None
        self.clock.observe(job)
        remaining = self.clock.remaining()
        if remaining <= 0:
            raise WaitTimeoutError(self.job_id, job.status, self.clock.total())
        pause = min(self._delay, remaining)
        self._delay = min(self._delay * 1.5, self._max_interval)
        return pause


_WAIT_OPTIONS = frozenset({"timeout", "interval", "max_interval", "on_progress"})


def split_run_options(options: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """jobs.run(**options) -> (create kwargs, wait kwargs)."""
    create = {k: v for k, v in options.items() if k not in _WAIT_OPTIONS}
    wait = {k: v for k, v in options.items() if k in _WAIT_OPTIONS}
    return create, wait


def core_options(api_key: Optional[str], *, base_url: str, timeout: float, app: Optional[str]) -> Dict[str, Any]:
    """The generated core's constructor kwargs, shared by both clients. Its own retries are off: `_call` owns them."""
    if app is not None and not _APP_NAME.match(app):
        raise ValueError('"app" must be 1-32 letters, digits or . _ + -')
    key = api_key if api_key is not None else (os.environ.get("RENDOBAR_API_KEY") or None)
    return {
        "base_url": base_url,
        "token": key,
        "headers": {"X-Rendobar-Client": _client_header(app)},
        "timeout": timeout,
        "max_retries": 0,
    }


class _Fetched:
    """A downloaded body with the headers the deprecation check reads."""

    def __init__(self, headers: Mapping[str, str], data: bytes) -> None:
        self.headers = headers
        self.data = data


class Rendobar:
    """The Rendobar API client.

    >>> from rendobar import Rendobar
    >>> with Rendobar() as rb:  # reads RENDOBAR_API_KEY
    ...     job = rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})
    >>> job.status
    'complete'

    `max_retries` bounds the retries of a 429, a 5xx or a failed connection.
    Use it as a context manager, or call `close()`, to release its connections.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        app: Optional[str] = None,
        on_deprecation: Optional[Callable[[DeprecationNotice], None]] = None,
    ) -> None:
        self._core = GeneratedClient(**core_options(api_key, base_url=base_url, timeout=timeout, app=app))
        self._max_retries = max_retries
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = Jobs(self)
        self.account = Account(self)

    def close(self) -> None:
        """Close the underlying HTTP connections. The client cannot be used after."""
        self._core._client_wrapper.httpx_client.httpx_client.close()

    def __enter__(self) -> "Rendobar":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        self.close()

    # ── shared plumbing ──────────────────────────────────────────────

    def _note(self, response: Any, method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    def _call(self, method: str, path: str, fn: Callable[[], Any]) -> Any:
        """One API call: retried per `retry_delay`, failures raised as RendobarError, deprecation noted."""
        attempt = 0
        while True:
            try:
                response = fn()
            except _CORE_FAILURES as err:
                delay = retry_delay(err, attempt, self._max_retries)
                if delay is None:
                    raise to_public(err) from err
                attempt += 1
                time.sleep(delay)
                continue
            self._note(response, method, path)
            return response.data


class Jobs:
    """Submit jobs, follow them to the end, and read their output."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.jobs.with_raw_response

    def types(self) -> List[Any]:
        """Every live job type, with its use cases. Public: needs no API key."""
        return list(self._client._call("GET", "/jobs/types", self._raw.list_job_types).data)

    def schema(self, type: str) -> Any:
        """One job type's params: `fields`, `inputs` and the full `json_schema`. Public: needs no API key."""
        return self._client._call("GET", f"/jobs/types/{type}/schema", lambda: self._raw.get_job_type_schema(type)).data

    def _job(self, method: str, path: str, fn: Callable[[], Any]) -> Any:
        try:
            return self._client._call(method, path, fn).data
        except ResponseValidationError as err:
            return one_job(err)

    def create(
        self,
        type: str,
        params: Optional[Mapping[str, Any]] = None,
        inputs: Optional[Mapping[str, Any]] = None,
        *,
        idempotency_key: Optional[str] = None,
        label: Optional[str] = None,
        destinations: Optional[Sequence[str]] = None,
        callback: Optional[Mapping[str, Any]] = None,
        force_async: Optional[bool] = None,
    ) -> Any:
        """Submit a job and return it as created (`id`, `status`).

        The submit is safe to retry: with no `idempotency_key`, one is generated
        for this call and sent on every retry, so a lost response cannot become a
        second job. Pass your own key (an order id) to make separate calls safe
        to repeat too. Keys never expire.
        """
        request = build_submit(type, params, inputs, idempotency_key=idempotency_key, label=label,
                               destinations=destinations, callback=callback, force_async=force_async)
        return self._job("POST", "/jobs", lambda: self._raw.submit_job(request=request))

    def get(self, job_id: str) -> Any:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        return self._job("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(job_id))

    def list(self, *, status: Optional[str] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page."""
        try:
            res = self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        except ResponseValidationError as err:
            return job_page(err)
        return Page(list(res.data), res.meta)

    def list_all(self, *, status: Optional[str] = None, type: Optional[str] = None, page_size: int = 100) -> Iterator[Any]:
        """Every matching job, fetching pages as you iterate."""
        offset = 0
        while True:
            page = self.list(status=status, type=type, limit=page_size, offset=offset)
            yield from page.data
            offset += len(page.data)
            total = getattr(page.meta, "total", None)
            if not page.data or (total is not None and offset >= total):
                return

    def cancel(self, job_id: str) -> Any:
        """Cancel a job that has not finished."""
        return self._job("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(job_id))

    def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        def fetch() -> _Fetched:
            with self._raw.download_job_output(job_id) as response:
                return _Fetched(response.headers, b"".join(response.data))

        return self._client._call("GET", f"/jobs/{job_id}/download", fetch)

    def wait(
        self,
        job_id: str,
        *,
        timeout: Optional[float] = None,
        interval: float = 2.0,
        max_interval: float = 10.0,
        on_progress: Optional[Callable[[Any], None]] = None,
        throw_on_failure: bool = False,
    ) -> Any:
        """Poll until the job is complete, failed or cancelled, and return it.

        With no `timeout`, the wait allows five minutes, extended once the job
        reports its own execution budget (its `timeout_ms`, your plan's per-job
        limit) to that budget plus two minutes for upload and delivery, counted
        from the poll that saw it. So a long job is not reported as timed out
        while it runs, and a job stuck in the queue still ends the wait.
        """
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval, throw_on_failure=throw_on_failure)
        while True:
            job = self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            pause = poll.step(job)
            if pause is None:
                return job
            time.sleep(pause)

    def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *, throw_on_failure: bool = True, **options: Any) -> Any:
        """Submit a job and wait for it. Raises `JobFailedError` if it fails, unless `throw_on_failure=False`."""
        create, wait = split_run_options(options)
        created = self.create(type, params, inputs, **create)
        return self.wait(created.id, throw_on_failure=throw_on_failure, **wait)


class Account:
    """What this API key's workspace may do."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client

    def capabilities(self) -> Any:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return self._client._call("GET", "/account/capabilities", raw.get_account_capabilities).data

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
from typing import Any, Callable, Dict, Iterator, List, Literal, Mapping, Optional, Protocol, Sequence, Tuple, Type, TypeVar, Union, get_args, overload

import httpx
import pydantic

from ._errors import (
    InvalidArgumentError,
    JobFailedError,
    ResponseValidationError,
    WaitTimeoutError,
    api_key_error,
    normalize,
    parse_retry_after,
    to_public,
)
from ._generated.client import GeneratedClient
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError as _GeneratedParsingError
from ._generated.core.pydantic_utilities import parse_obj_as
from ._generated.types.job import Job as _Job
from ._generated.types.submit_any_job import SubmitAnyJob
from ._models import (
    AccountCapabilities,
    Job,
    JobCancellation,
    JobCancelled,
    JobComplete,
    JobCreated,
    JobFailed,
    JobReplayed,
    JobType,
    JobTypeSchema,
    PageMeta,
)
from ._version import __version__

DEFAULT_BASE_URL = "https://api.rendobar.com"
JobStatus = Literal["waiting", "dispatched", "running", "complete", "failed", "cancelled"]  # every status this SDK knows
KNOWN_STATUSES = frozenset(get_args(JobStatus))
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


SomeJob = Union[Job, UnknownJob]  # what a call that reads jobs returns
FinishedJob = Union[JobComplete, JobFailed, JobCancelled]  # what jobs.wait() returns


class Page:
    """One page of jobs.list(): `data` plus `meta` (`total`, `page`, `limit`)."""

    def __init__(self, data: List[SomeJob], meta: PageMeta) -> None:
        self.data = data
        self.meta = meta

    def __iter__(self) -> Iterator[SomeJob]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"Page({len(self.data)} jobs, total={self.meta.total}, page={self.meta.page}, limit={self.meta.limit})"


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
    try:
        return SubmitAnyJob.model_validate(body)  # the untyped variant: valid for every job type
    except pydantic.ValidationError as err:
        raise InvalidArgumentError(f"The job cannot be submitted: {err}") from None


def _is_newer_job(raw: Any) -> bool:
    """A job-shaped body (it has an id) whose status this SDK does not know."""
    return isinstance(raw, Mapping) and isinstance(raw.get("id"), str) and str(raw.get("status", "")) not in KNOWN_STATUSES


def job_from(raw: Any, err: ResponseValidationError) -> SomeJob:
    """One job as the API sent it: the typed model, or `UnknownJob` when its status is newer than this SDK.

    A job with a status this SDK knows that still does not parse is a real
    mismatch, and raises `err` rather than hiding it.
    """
    try:
        job: Job = parse_obj_as(_Job, raw)  # type: ignore[arg-type]  # `_Job` is an Annotated union, which parse_obj_as reads at runtime
        return job
    except pydantic.ValidationError:
        if _is_newer_job(raw):
            return UnknownJob(raw)
        raise err from None


def one_job(err: ResponseValidationError) -> UnknownJob:
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
        meta = parse_obj_as(PageMeta, body.get("meta"))
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

    def observe(self, job: SomeJob) -> None:
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

    After each poll, `finished(job)` returns the job when the wait is over (or
    raises `JobFailedError` when asked to), and otherwise `pause(job)` returns
    the seconds to sleep before the next poll, or raises `WaitTimeoutError`.
    """

    def __init__(self, job_id: str, *, timeout: Optional[float], interval: float, max_interval: float,
                 throw_on_failure: bool, clock: Callable[[], float] = time.monotonic) -> None:
        self.job_id = job_id
        self.clock = WaitClock(timeout, clock=clock)
        self._delay = interval
        self._max_interval = max_interval
        self._throw = throw_on_failure

    def finished(self, job: SomeJob) -> Optional[FinishedJob]:
        if isinstance(job, (JobFailed, JobCancelled)):
            if self._throw:
                raise JobFailedError(job)
            return job
        if isinstance(job, JobComplete):
            return job
        return None

    def pause(self, job: SomeJob) -> float:
        self.clock.observe(job)
        remaining = self.clock.remaining()
        if remaining <= 0:
            raise WaitTimeoutError(self.job_id, job.status, self.clock.total())
        pause = min(self._delay, remaining)
        self._delay = min(self._delay * 1.5, self._max_interval)
        return pause


def resolve_api_key(api_key: Optional[str]) -> Optional[str]:
    """The client's key: `api_key`, else RENDOBAR_API_KEY, as given. `api_key_error` says whether it can be used."""
    return api_key if api_key is not None else os.environ.get("RENDOBAR_API_KEY")


def require_key(key: Optional[str]) -> None:
    """Raises the AuthenticationError for a call that needs a key when `key` is missing or not a Rendobar key."""
    problem = api_key_error(key)
    if problem is not None:
        raise problem


_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def path_segment(name: str, value: str) -> str:
    """`value` when it is safe as one URL path segment (a job id, a job type), else InvalidArgumentError."""
    if not isinstance(value, str) or not _PATH_SEGMENT.match(value) or value in (".", ".."):
        raise InvalidArgumentError(f"{name} must be letters, digits, '.', '_' or '-', such as job_abc123. Got {value!r}.")
    return value


def page_window(limit: Optional[int], offset: Optional[int]) -> None:
    """InvalidArgumentError for a page size below 1 or a negative offset. The API sets the maximum."""
    if limit is not None and limit < 1:
        raise InvalidArgumentError(f"limit must be 1 or more. Got {limit}.")
    if offset is not None and offset < 0:
        raise InvalidArgumentError(f"offset must be 0 or more. Got {offset}.")


def core_options(key: Optional[str], *, base_url: str, timeout: float, app: Optional[str]) -> Dict[str, Any]:
    """The generated core's constructor kwargs, shared by both clients. Its own retries are off: `_call` owns them.

    A key `api_key_error` refuses is not sent at all: public calls then go out without one.
    """
    if app is not None and not _APP_NAME.match(app):
        raise InvalidArgumentError('"app" must be 1-32 letters, digits or . _ + -')
    return {
        "base_url": base_url,
        "token": key if api_key_error(key) is None else None,
        "headers": {"X-Rendobar-Client": _client_header(app)},
        "timeout": timeout,
        "max_retries": 0,
    }


class _Fetched:
    """A downloaded body with the headers the deprecation check reads."""

    def __init__(self, headers: Mapping[str, str], data: bytes) -> None:
        self.headers = headers
        self.data = data


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Response(Protocol[T_co]):
    """What a call through the core returns: the core's HttpResponse, or a `_Fetched` download."""

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def data(self) -> T_co: ...


class Envelope(Protocol[T_co]):
    """A response body that wraps its payload in `data`."""

    @property
    def data(self) -> T_co: ...


# What jobs.wait() and jobs.run() accept for `on_progress`: called with the job after every poll.
ProgressCallback = Callable[[SomeJob], None]


class Rendobar:
    """The Rendobar API client.

    >>> from rendobar import Rendobar
    >>> with Rendobar() as rb:  # reads RENDOBAR_API_KEY
    ...     job = rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})
    >>> job.status
    'complete'

    Args:
        api_key: Your API key. Defaults to the RENDOBAR_API_KEY environment
            variable. With neither set, every call that needs a key raises
            `AuthenticationError` (code `MISSING_API_KEY`) before sending
            anything. `jobs.types()` and `jobs.schema()` need no key.
        base_url: The API to talk to. Defaults to https://api.rendobar.com.
        timeout: Seconds one HTTP request may take.
        max_retries: How many times a 429, a 5xx or a failed connection is retried.
        app: Your app's name (1-32 letters, digits or `. _ + -`), sent in the
            `X-Rendobar-Client` header so your jobs show where they came from.
        on_deprecation: Called once per deprecated endpoint this client calls.
            Without it, a `RendobarDeprecationWarning` is emitted instead.

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
        self._api_key = resolve_api_key(api_key)
        self._core = GeneratedClient(**core_options(self._api_key, base_url=base_url, timeout=timeout, app=app))
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

    def _note(self, response: Response[object], method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    def _call(self, method: str, path: str, fn: Callable[[], Response[T]], *, public: bool = False) -> T:
        """One API call: retried per `retry_delay`, failures raised as RendobarError, deprecation noted.

        A call that needs a key (every one but `public`) raises at once when the client has none.
        """
        if not public:
            require_key(self._api_key)
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

    def types(self) -> List[JobType]:
        """Every live job type, with its use cases. Public: needs no API key."""
        return list(self._client._call("GET", "/jobs/types", self._raw.list_job_types, public=True).data)

    def schema(self, type: str) -> JobTypeSchema:
        """One job type's params: `fields`, `inputs` and the full `json_schema`. Public: needs no API key."""
        return self._client._call("GET", f"/jobs/types/{type}/schema", lambda: self._raw.get_job_type_schema(path_segment("type", type)), public=True).data

    def _job(self, method: str, path: str, fn: Callable[[], Response[Envelope[T]]]) -> Union[T, UnknownJob]:
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
    ) -> Union[JobCreated, JobReplayed, UnknownJob]:
        """Submit a job and return it as created (`id`, `status`), without waiting.

        Args:
            type: The job type, such as "ffmpeg" or "ffprobe". `jobs.types()` lists every live one.
            params: The job type's params. `jobs.schema(type)` describes them.
            inputs: Named input files, as URLs, for job types that take them.
            idempotency_key: Makes the submit safe to repeat. A second submit
                with the same key returns the first one's job (a `JobReplayed`)
                instead of creating another. Reusing a key with different
                params raises `ConflictError` (409, code CONFLICT). Keys never
                expire. Default: a key generated for this call and sent on
                every retry of it, so a lost response cannot become a second job.
            label: A short name for the job, shown in the dashboard and returned as `job.label`.
            destinations: Where to deliver the output once the job completes,
                as `storage://<id>[/<folder or path>]`.
            callback: A URL Rendobar POSTs the job to when it ends:
                `{"url": ..., "headers": {...}, "verify": True, "events": ["job.started"]}`.
            force_async: Queue the job even when its type can finish during the request.
        """
        request = build_submit(type, params, inputs, idempotency_key=idempotency_key, label=label,
                               destinations=destinations, callback=callback, force_async=force_async)
        return self._job("POST", "/jobs", lambda: self._raw.submit_job(request=request))

    def get(self, job_id: str) -> SomeJob:
        """The job now. A status newer than this SDK comes back as `UnknownJob`.

        Narrow with isinstance to read what only one status has, such as
        `output` on `JobComplete` and `error` on `JobFailed`.
        """
        return self._job("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(path_segment("job_id", job_id)))

    def list(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page.

        `limit` is the page size (1 or more, the API sets the maximum) and `offset` the jobs to skip.
        """
        page_window(limit, offset)
        try:
            res = self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        except ResponseValidationError as err:
            return job_page(err)
        jobs: List[SomeJob] = list(res.data)
        return Page(jobs, res.meta)

    def list_all(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, page_size: int = 100) -> Iterator[SomeJob]:
        """Every matching job, fetching pages as you iterate."""
        offset = 0
        while True:
            page = self.list(status=status, type=type, limit=page_size, offset=offset)
            yield from page.data
            offset += len(page.data)
            if not page.data or offset >= page.meta.total:
                return

    def cancel(self, job_id: str) -> Union[JobCancellation, UnknownJob]:
        """Cancel a job that has not finished."""
        return self._job("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(path_segment("job_id", job_id)))

    def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        def fetch() -> _Fetched:
            with self._raw.download_job_output(path_segment("job_id", job_id)) as response:
                return _Fetched(response.headers, b"".join(response.data))

        return self._client._call("GET", f"/jobs/{job_id}/download", fetch)

    @overload
    def wait(self, job_id: str, *, timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
             on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True]) -> JobComplete: ...

    @overload
    def wait(self, job_id: str, *, timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
             on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool = False) -> FinishedJob: ...

    def wait(
        self,
        job_id: str,
        *,
        timeout: Optional[float] = None,
        interval: float = 2.0,
        max_interval: float = 10.0,
        on_progress: Optional[ProgressCallback] = None,
        throw_on_failure: bool = False,
    ) -> FinishedJob:
        """Poll until the job is complete, failed or cancelled, and return it.

        Args:
            job_id: The job to wait for.
            timeout: Seconds to wait before raising `WaitTimeoutError` (the job
                may still finish). Default: five minutes, extended once the job
                reports its own execution budget (`timeout_ms`, your plan's
                per-job limit) to that budget plus two minutes for upload and
                delivery, counted from the poll that saw it. So a long job is
                not cut off while it runs, and a job stuck in the queue still
                ends the wait.
            interval: Seconds before the second poll. Each later pause is 1.5 times longer.
            max_interval: The longest pause between polls, in seconds.
            on_progress: Called with the job after every poll.
            throw_on_failure: Raise `JobFailedError` when the job fails or is
                cancelled. Default: return that job instead.
        """
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval, throw_on_failure=throw_on_failure)
        while True:
            job = self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            done = poll.finished(job)
            if done is not None:
                return done
            time.sleep(poll.pause(job))

    @overload
    def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *,
            idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[Sequence[str]] = None,
            callback: Optional[Mapping[str, Any]] = None, force_async: Optional[bool] = None,
            timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
            on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True] = True) -> JobComplete: ...

    @overload
    def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *,
            idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[Sequence[str]] = None,
            callback: Optional[Mapping[str, Any]] = None, force_async: Optional[bool] = None,
            timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
            on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool) -> FinishedJob: ...

    def run(
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
        timeout: Optional[float] = None,
        interval: float = 2.0,
        max_interval: float = 10.0,
        on_progress: Optional[ProgressCallback] = None,
        throw_on_failure: bool = True,
    ) -> FinishedJob:
        """Submit a job and wait for it: `jobs.create()`, then `jobs.wait()`.

        Returns the `JobComplete`. Raises `JobFailedError` if the job fails or
        is cancelled, unless `throw_on_failure=False`, which returns that job.

        Args:
            type: The job type, such as "ffmpeg" or "ffprobe". `jobs.types()` lists every live one.
            params: The job type's params. `jobs.schema(type)` describes them.
            inputs: Named input files, as URLs, for job types that take them.
            idempotency_key: Makes the submit safe to repeat (see `jobs.create()`).
                Reusing a key with different params raises `ConflictError` (409).
            label: A short name for the job, shown in the dashboard.
            destinations: Where to deliver the output, as `storage://<id>[/<folder or path>]`.
            callback: A URL Rendobar POSTs the job to when it ends (see `jobs.create()`).
            force_async: Queue the job even when its type can finish during the request.
            timeout: Seconds to wait (see `jobs.wait()`). Default: five minutes,
                extended to the job's own execution budget once it reports one.
            interval: Seconds before the second poll. Each later pause is 1.5 times longer.
            max_interval: The longest pause between polls, in seconds.
            on_progress: Called with the job after every poll.
            throw_on_failure: Raise `JobFailedError` when the job fails or is cancelled. Default: True.
        """
        created = self.create(type, params, inputs, idempotency_key=idempotency_key, label=label,
                              destinations=destinations, callback=callback, force_async=force_async)
        return self.wait(created.id, timeout=timeout, interval=interval, max_interval=max_interval,
                         on_progress=on_progress, throw_on_failure=throw_on_failure)


class Account:
    """What this API key's workspace may do."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client

    def capabilities(self) -> AccountCapabilities:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return self._client._call("GET", "/account/capabilities", raw.get_account_capabilities).data

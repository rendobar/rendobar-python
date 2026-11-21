"""The Rendobar client.

A thin, hand-written layer over the generated core in `_generated` (Fern, from
the published OpenAPI document). The core supplies models, timeouts and HTTP.
It is built with its own retries off: this layer owns them, so only 429, 500,
502, 503, 504 and connection failures are retried (never a 409 or 408). It
adds what a spec cannot say:

- the same method names as `@rendobar/sdk` (`jobs.create`, `jobs.run`, ...),
- responses unwrapped from the `{data}` envelope,
- one idempotency key per `jobs.create()` call, so a retried submit cannot
  create a second job,
- `jobs.wait()` / `jobs.run()`, `jobs.list_all()`, a streamed `jobs.download()`,
- `RENDOBAR_API_KEY` from the environment, the `X-Rendobar-Client` header,
- `Deprecation` notices, and a job whose status is newer than this SDK
  (`UnknownJob`, from any call that returns jobs),
- one error hierarchy (`RendobarError`) for API errors, transport failures,
  bad arguments and responses this version cannot read.

Everything that is not I/O lives here as plain helpers (`retry_delay`,
`WaitPoll`, `one_job`, `job_page`, `submit_body`, ...) that `_async_client`
reuses, so the sync and async clients behave identically.

Behaviour is held to the shared conformance scenarios (tests/test_conformance.py).
"""
# pyright: strict, reportPrivateUsage=false
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
from typing import (
    IO,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import TypedDict

import httpx
import pydantic

from ._errors import (
    APIConnectionError,
    InvalidArgumentError,
    JobFailedError,
    RendobarError,
    ResponseValidationError,
    WaitTimeoutError,
    api_key_error,
    as_list,
    as_mapping,
    client_closed,
    is_text,
    normalize,
    parse_retry_after,
    to_public,
)
from ._generated.client import GeneratedClient
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError as _GeneratedParsingError
from ._generated.jobs.requests.submit_job_request import SubmitJobRequestParams
from ._generated.types.job import Job as _Job
from ._models import (
    KNOWN_STATUSES,
    AccountCapabilities,
    Callback,
    FinishedJob,
    Job,
    JobCancellation,
    JobCancelled,
    JobComplete,
    JobCompletedOnSubmit,
    JobCreated,
    JobFailed,
    JobReplayed,
    JobStatus,
    JobType,
    JobTypeSchema,
    PageMeta,
    SomeJob,
    SubmitJob,
    Submitted,
    UnknownJob,
    UntypedJob,
)
from ._version import __version__

DEFAULT_BASE_URL = "https://api.rendobar.com"
_DEFAULT_WAIT_TIMEOUT = 300.0  # seconds, until the job reports its own budget
_WAIT_GRACE = 120.0  # headroom past the job's budget for upload and callback
_APP_NAME = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")
_BACKOFF_BASE = 0.5  # seconds before the first retry with no Retry-After
_BACKOFF_CAP = 8.0
_MAX_RETRY_AFTER = 60.0  # a longer Retry-After is raised, with `retry_after` set, for the caller to schedule
RETRIED_STATUSES = frozenset({429, 500, 502, 503, 504})

# What a call through the core can fail with. Everything else is a bug and propagates as is.
_CORE_FAILURES: Tuple[Type[BaseException], ...] = (_GeneratedApiError, _GeneratedParsingError, httpx.TransportError)

# Where jobs.download() writes: a file path (created or replaced) or a binary file you opened.
DownloadTarget = Union[str, "os.PathLike[str]", IO[bytes]]


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


class _Deprecations:
    """Reports each deprecated route once per client. Shared by the sync and async clients.

    Reporting never changes the call: a handler that raises, or a header no date
    can hold, must not turn a request that succeeded into an exception.
    """

    def __init__(self, handler: Optional[Callable[[DeprecationNotice], None]]) -> None:
        self._handler = handler
        self._seen: Set[str] = set()

    def note(self, response: Response[object], method: str, path: str) -> None:
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


# ── arguments, checked before any request ──────────────────────────────

_JOB_KEYS = frozenset({"type", "params", "inputs"})  # what to run; the submit options are keyword arguments


def _job_fields(job: object) -> Dict[str, object]:
    """The `type`, `params` and `inputs` of a typed job dict, checked at runtime too (the type check is the user's to run)."""
    fields = as_mapping(job)
    if fields is None:
        raise InvalidArgumentError(f'job must be a job dict, such as {{"type": "ffprobe", "params": {{...}}}}, or an UntypedJob. Got {type(job).__name__}.')
    extra = sorted(set(fields) - _JOB_KEYS)
    if extra:
        raise InvalidArgumentError(f"{extra} are not part of a job. Pass submit options to create() or run(): create(job, label=...).")
    kind = fields.get("type")
    if not isinstance(kind, str) or not kind:
        raise InvalidArgumentError(f"job type must be a non-empty string. Got {kind!r}.")
    out: Dict[str, object] = {"type": kind}
    for name in ("params", "inputs"):
        if name in fields:
            value = as_mapping(fields[name])
            if value is None:
                raise InvalidArgumentError(f"job {name} must be a dict with string keys. Got {type(fields[name]).__name__}.")
            out[name] = dict(value)
    return out


def submit_body(
    job: Union[SubmitJob, UntypedJob],
    *,
    idempotency_key: str,
    label: Optional[str],
    destinations: Optional[List[str]],
    callback: Optional[Callback],
    force_async: Optional[bool],
) -> SubmitJobRequestParams:
    """The submit body. `idempotency_key` is the caller's, or one `generate_idempotency_key()` made for this call."""
    if isinstance(job, UntypedJob):
        body = _job_fields({"type": job.type, "params": job.params, "inputs": job.inputs})
    else:
        body = _job_fields(job)
    body["idempotency_key"] = idempotency_key
    if label is not None:
        if not is_text(label):
            raise InvalidArgumentError(f"label must be a string. Got {type(label).__name__}.")
        body["label"] = label
    if destinations is not None:
        items = None if isinstance(destinations, str) else as_list(destinations)
        if items is None or not all(isinstance(item, str) for item in items):
            raise InvalidArgumentError(f'destinations must be a list of strings, such as ["storage://prod-media"]. Got {destinations!r}.')
        body["destinations"] = items
    if callback is not None:
        hook = as_mapping(callback)
        if hook is None or not isinstance(hook.get("url"), str):
            raise InvalidArgumentError('callback must be a dict with a "url", such as {"url": "https://example.com/hook"}.')
        body["callback"] = dict(hook)
    if force_async is not None:
        if force_async is not True and force_async is not False:
            raise InvalidArgumentError(f"force_async must be True or False. Got {force_async!r}.")
        body["force_async"] = force_async
    # The fields were checked above. The core serialises this dict by the union's annotations
    # (snake_case to the wire's camelCase); a TypedDict union cannot be built from a dict without a cast.
    return cast(SubmitJobRequestParams, body)


_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def path_segment(name: str, value: str) -> str:
    """`value` when it is safe as one URL path segment (a job id, a job type), else InvalidArgumentError."""
    if not is_text(value) or not _PATH_SEGMENT.match(value) or value in (".", ".."):
        raise InvalidArgumentError(f"{name} must be letters, digits, '.', '_' or '-', such as job_abc123. Got {value!r}.")
    return value


def _whole(name: str, value: object, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidArgumentError(f"{name} must be a whole number of {minimum} or more. Got {value!r}.")


def page_window(limit: Optional[int], offset: Optional[int]) -> None:
    """InvalidArgumentError for a page size below 1, a negative offset, or either not a whole number. The API sets the maximum."""
    if limit is not None:
        _whole("limit", limit, 1)
    if offset is not None:
        _whole("offset", offset, 0)


def list_filters(status: Optional[str], kind: Optional[str]) -> None:
    """InvalidArgumentError for a list filter that is not a string."""
    for name, value in (("status", status), ("type", kind)):
        if value is not None and not is_text(value):
            raise InvalidArgumentError(f"{name} must be a string. Got {type(value).__name__}.")


def _seconds(name: str, value: object, *, allow_zero: bool) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or (value == 0 and not allow_zero):
        raise InvalidArgumentError(f"{name} must be a {'non-negative' if allow_zero else 'positive'} number of seconds. Got {value!r}.")


def wait_options(timeout: Optional[float], interval: float, max_interval: float) -> None:
    """InvalidArgumentError for a negative timeout, or a pause between polls that is not a positive number of seconds."""
    if timeout is not None:
        _seconds("timeout", timeout, allow_zero=True)
    _seconds("interval", interval, allow_zero=False)
    _seconds("max_interval", max_interval, allow_zero=False)


# ── responses ─────────────────────────────────────────────────────────

def _is_newer_job(raw: object) -> bool:
    """A job-shaped body (it has an id) whose status this SDK does not know."""
    job = as_mapping(raw)
    return job is not None and isinstance(job.get("id"), str) and str(job.get("status", "")) not in KNOWN_STATUSES


_JOB_ADAPTER: pydantic.TypeAdapter[Job] = pydantic.TypeAdapter(_Job)


def job_from(raw: object, err: ResponseValidationError) -> SomeJob:
    """One job as the API sent it: the typed model, or `UnknownJob` when its status is newer than this SDK.

    A job with a status this SDK knows that still does not parse is a real
    mismatch, and raises `err` rather than hiding it.
    """
    try:
        return _JOB_ADAPTER.validate_python(raw)
    except pydantic.ValidationError:
        job = as_mapping(raw)
        if job is not None and _is_newer_job(job):
            return UnknownJob(job)
        raise err from None


def submitted(response: httpx.Response) -> Submitted:
    """The submit's answer, by status: 201 a JobCreated, 200 a JobCompletedOnSubmit or (with `idempotent`) a JobReplayed.

    The core types only the 200 body, so this reads the body itself.
    """
    try:
        decoded: object = response.json()
    except ValueError:
        decoded = response.text
    body = as_mapping(decoded)
    data = as_mapping(body.get("data")) if body is not None else None
    unread = ResponseValidationError(
        f"The API answered the submit with {response.status_code} and a body this SDK cannot read. Upgrade rendobar, or read `body`.",
        status_code=response.status_code, body=decoded, headers=dict(response.headers),
    )
    if data is None:
        raise unread
    try:
        if response.status_code == 201:
            return JobCreated.model_validate(data)
        if data.get("idempotent") is True:
            return JobReplayed.model_validate(data)
        return JobCompletedOnSubmit.model_validate(data)
    except pydantic.ValidationError:
        raise unread from None


Model = TypeVar("Model", bound=pydantic.BaseModel)


def output_data(job: JobComplete, model: Type[Model]) -> Model:
    """`job.output.data` read as `model`, the result type of the job's type, such as `FfprobeResult` for ffprobe.

        probe = rb.jobs.run({"type": "ffprobe", "params": {"command": url}})
        result = output_data(probe, FfprobeResult)

    Raises ResponseValidationError when the data is not that shape (such as a
    result type that belongs to another job type). Unknown fields are kept.
    """
    try:
        return model.model_validate(job.output.data)
    except pydantic.ValidationError:
        raise ResponseValidationError(
            f"Job {job.id} ({job.type}) has output data that is not a {model.__name__}.",
            status_code=None, body=job.output.data,
        ) from None


def one_job(err: ResponseValidationError) -> UnknownJob:
    """Recovers a single-job response (get, create, cancel) the core could not parse."""
    body = as_mapping(err.body)
    data = as_mapping(body.get("data")) if body is not None else None
    if data is not None and _is_newer_job(data):
        return UnknownJob(data)
    raise err


_META_ADAPTER: pydantic.TypeAdapter[PageMeta] = pydantic.TypeAdapter(PageMeta)


def job_page(err: ResponseValidationError) -> Page:
    """Recovers a list response the core could not parse: each job on its own, so one new status costs one item, not the page."""
    body = as_mapping(err.body)
    data = as_list(body.get("data")) if body is not None else None
    if body is None or data is None:
        raise err
    try:
        meta = _META_ADAPTER.validate_python(body.get("meta"))
    except pydantic.ValidationError:
        raise err from None
    return Page([job_from(item, err) for item in data], meta)


# ── retries ───────────────────────────────────────────────────────────

def retry_delay(err: BaseException, attempt: int, max_retries: int, *, deadline: Optional[float] = None,
                clock: Callable[[], float] = time.monotonic, rand: Callable[[], float] = random.random) -> Optional[float]:
    """Seconds to wait before retry number `attempt + 1`, or None to raise now.

    `deadline` (on `clock`, monotonic seconds) is the caller's: a retry that
    would sleep past it is not made, and the error raises at once.

    Retried: 429, 500, 502, 503 and 504 (after `Retry-After` when sent, else
    exponential backoff with jitter) and connection failures where the request
    never reached the API. Never retried: any other status (a 409 conflict, a
    501, a 408), a read timeout (the API may still be working on it), and a
    response this SDK cannot read.
    """
    if attempt >= max_retries:
        return None
    err = normalize(err)
    if isinstance(err, _GeneratedApiError):
        if err.status_code not in RETRIED_STATUSES:
            return None
        headers = {k.lower(): v for k, v in (err.headers or {}).items()}
        after = parse_retry_after(headers.get("retry-after"))
        if after is not None:
            return _within(after if after <= _MAX_RETRY_AFTER else None, deadline, clock)
    elif not isinstance(err, (httpx.ConnectError, httpx.ConnectTimeout)):
        return None
    backoff = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
    return _within(backoff * (0.75 + 0.5 * rand()), deadline, clock)


def _within(delay: Optional[float], deadline: Optional[float], clock: Callable[[], float]) -> Optional[float]:
    return None if delay is None or (deadline is not None and clock() + delay > deadline) else delay


_MAY_HAVE_CREATED = frozenset({429}) | frozenset(range(500, 600))


def mark_cut_off(err: RendobarError, idempotency_key: str) -> None:
    """Gives a failed submit the key it sent when the job may exist anyway, so resubmitting with it returns that job.

    That is any failure with no answer (connection, timeout), a 429 or 5xx after
    the last retry, and a success response this SDK could not read.
    """
    if isinstance(err, (APIConnectionError, ResponseValidationError)) or err.status_code in _MAY_HAVE_CREATED:
        err.idempotency_key = idempotency_key


# ── waiting ───────────────────────────────────────────────────────────

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
        budget_ms: object = None if isinstance(job, UnknownJob) else job.timeout_ms
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
    the seconds to sleep before the next poll, or raises `WaitTimeoutError`. A
    status this SDK does not know (`UnknownJob`) is over when the job says it
    is `terminal`, and otherwise polled until the deadline.
    """

    def __init__(self, job_id: str, *, timeout: Optional[float], interval: float, max_interval: float,
                 throw_on_failure: bool, clock: Callable[[], float] = time.monotonic) -> None:
        self.job_id = job_id
        self.clock = WaitClock(timeout, clock=clock)
        self._delay = interval
        self._max_interval = max_interval
        self._throw = throw_on_failure

    def finished(self, job: SomeJob) -> Optional[FinishedJob]:
        if isinstance(job, JobComplete):
            return job
        if isinstance(job, (JobFailed, JobCancelled)) or (isinstance(job, UnknownJob) and job.terminal):
            if self._throw:
                raise JobFailedError(job)
            return job
        return None

    def pause(self, job: SomeJob) -> float:
        self.clock.observe(job)
        remaining = self.clock.remaining()
        if remaining <= 0:
            raise WaitTimeoutError(self.job_id, job.status, self.clock.total(), job)
        pause = min(self._delay, remaining)
        self._delay = min(self._delay * 1.5, self._max_interval)
        return pause


# ── the client's key and core ─────────────────────────────────────────

def resolve_api_key(api_key: Optional[str]) -> Optional[str]:
    """The client's key: `api_key`, else RENDOBAR_API_KEY, as given. `api_key_error` says whether it can be used."""
    return api_key if api_key is not None else os.environ.get("RENDOBAR_API_KEY")


def require_key(key: Optional[str]) -> None:
    """Raises the AuthenticationError for a call that needs a key when `key` is missing or not a Rendobar key."""
    problem = api_key_error(key)
    if problem is not None:
        raise problem


class CoreOptions(TypedDict):
    """The generated core's constructor arguments this layer sets."""

    base_url: str
    token: Optional[str]
    headers: Dict[str, str]
    timeout: float
    max_retries: int


def core_options(key: Optional[str], *, base_url: str, timeout: float, app: Optional[str]) -> CoreOptions:
    """The generated core's constructor kwargs, shared by both clients. Its own retries are off: `_call` owns them.

    A key `api_key_error` refuses is not sent at all: public calls then go out without one.
    """
    if app is not None and not _APP_NAME.match(app):
        raise InvalidArgumentError('"app" must be 1-32 letters, digits or . _ + -')
    return CoreOptions(
        base_url=base_url,
        token=key if api_key_error(key) is None else None,
        headers={"X-Rendobar-Client": _client_header(app)},
        timeout=timeout,
        max_retries=0,
    )


# ── downloads ─────────────────────────────────────────────────────────

class _Fetched(Generic[T]):
    """A downloaded body's result with the headers the deprecation check reads."""

    def __init__(self, headers: Mapping[str, str], data: T) -> None:
        self.headers = headers
        self.data = data


class Sink:
    """Where a download's bytes go: the file the caller passed, or one opened (and on failure removed) here."""

    def __init__(self, to: DownloadTarget) -> None:
        self._path: Optional[str] = None
        if isinstance(to, (str, os.PathLike)):
            self._path = os.fspath(to)
            self.file: IO[bytes] = open(self._path, "wb")  # noqa: SIM115 (closed in finish/fail)
        else:
            self.file = to
        self.written = 0

    def write(self, chunk: bytes) -> None:
        self.file.write(chunk)
        self.written += len(chunk)

    def finish(self) -> int:
        if self._path is not None:
            self.file.close()
        return self.written

    def fail(self) -> None:
        if self._path is not None:
            self.file.close()
            try:
                os.remove(self._path)
            except OSError:
                pass


def body_failed(err: BaseException) -> RendobarError:
    """A failure after the body started. Raised as a RendobarError `_call` does not retry: the bytes so far are gone."""
    if isinstance(err, RendobarError):
        return err
    if isinstance(err, httpx.TransportError):
        return to_public(err)
    out = RendobarError(f"The download failed while writing: {err}", code="DOWNLOAD_FAILED")
    out.__cause__ = err
    return out


# What jobs.wait() and jobs.run() accept for `on_progress`: called with the job after every poll.
ProgressCallback = Callable[[SomeJob], None]


class Rendobar:
    """The Rendobar API client.

    >>> from rendobar import Rendobar
    >>> with Rendobar() as rb:  # reads RENDOBAR_API_KEY
    ...     job = rb.jobs.run({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}})
    >>> job.status
    'complete'

    Args:
        api_key: Your API key. Defaults to the RENDOBAR_API_KEY environment
            variable. With neither set, every call that needs a key raises
            `AuthenticationError` (code `MISSING_API_KEY`) before sending
            anything. `jobs.types()` and `jobs.schema()` need no key.
        base_url: The API to talk to. Defaults to https://api.rendobar.com.
        timeout: Seconds one HTTP request may take.
        max_retries: How many times a 429, a 500, 502, 503, 504 or a failed connection is retried.
        app: Your app's name (1-32 letters, digits or `. _ + -`), sent in the
            `X-Rendobar-Client` header so your jobs show where they came from.
        on_deprecation: Called once per deprecated endpoint this client calls.
            Without it, a `RendobarDeprecationWarning` is emitted instead.

    Use it as a context manager, or call `close()`, to release its connections.
    A call after `close()` raises RendobarError with code `CLIENT_CLOSED`.
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
        self._closed = False
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = Jobs(self)
        self.account = Account(self)

    def close(self) -> None:
        """Close the underlying HTTP connections. Every call after raises RendobarError (code `CLIENT_CLOSED`)."""
        self._closed = True
        self._core._client_wrapper.httpx_client.httpx_client.close()

    def __enter__(self) -> Rendobar:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        self.close()

    # ── shared plumbing ──────────────────────────────────────────────

    def _call(self, method: str, path: str, fn: Callable[[], Response[T]], *, public: bool = False, deadline: Optional[float] = None) -> T:
        """One API call: retried per `retry_delay`, failures raised as RendobarError, deprecation noted.

        A call that needs a key (every one but `public`) raises at once when the client has none.
        No retry sleeps past `deadline` (time.monotonic seconds).
        """
        if self._closed:
            raise client_closed()
        if not public:
            require_key(self._api_key)
        attempt = 0
        while True:
            try:
                response = fn()
            except _CORE_FAILURES as err:
                delay = retry_delay(err, attempt, self._max_retries, deadline=deadline)
                if delay is None:
                    raise to_public(err) from err
                attempt += 1
                time.sleep(delay)
                continue
            self._deprecations.note(response, method, path)
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
        name = path_segment("type", type)
        schema: JobTypeSchema = self._client._call("GET", f"/jobs/types/{name}/schema", lambda: self._raw.get_job_type_schema(name), public=True).data
        return schema

    def _job(self, method: str, path: str, fn: Callable[[], Response[Envelope[T]]], deadline: Optional[float] = None) -> Union[T, UnknownJob]:
        try:
            return self._client._call(method, path, fn, deadline=deadline).data
        except ResponseValidationError as err:
            return one_job(err)

    def create(
        self,
        job: Union[SubmitJob, UntypedJob],
        *,
        idempotency_key: Optional[str] = None,
        label: Optional[str] = None,
        destinations: Optional[List[str]] = None,
        callback: Optional[Callback] = None,
        force_async: Optional[bool] = None,
    ) -> Submitted:
        """Submit a job and return it as created (`id`, `status`), without waiting.

        Returns a `JobCreated` (status waiting), a `JobCompletedOnSubmit` for a job
        that finished during the request, or a `JobReplayed` when the idempotency
        key was used before.

        Args:
            job: What to run, typed per job type: `{"type": "ffprobe", "params": {"command": url}}`.
                A misspelt or missing param, a wrong value type or an unknown
                type fails your type checker. For a job type this SDK does not
                know yet, pass `UntypedJob(type, params)`.
            idempotency_key: Makes the submit safe to repeat. A second submit
                with the same key returns the first one's job (a `JobReplayed`)
                instead of creating another. Reusing a key with different
                params raises `ConflictError` (409, code CONFLICT). Keys never
                expire. Default: a key generated for this call and sent on
                every retry of it, so a lost response cannot become a second job.
            label: A short name for the job, shown in the dashboard and returned as `job.label`.
            destinations: Where to deliver the output once the job completes,
                as a list of `storage://<id>[/<folder or path>]`.
            callback: A URL Rendobar POSTs the job to when it ends:
                `{"url": ..., "headers": {...}, "verify": True, "events": ["job.started"]}`.
            force_async: Queue the job even when its type can finish during the request.
        """
        key = idempotency_key if idempotency_key is not None else generate_idempotency_key()
        request = submit_body(job, idempotency_key=key, label=label, destinations=destinations,
                              callback=callback, force_async=force_async)
        def submit() -> _Fetched[Submitted]:
            sent = self._raw.submit_job(request=request)
            return _Fetched(sent.headers, submitted(sent.response))

        try:
            return self._client._call("POST", "/jobs", submit)
        except RendobarError as err:
            mark_cut_off(err, key)
            raise

    def get(self, job_id: str) -> SomeJob:
        """The job now. A status newer than this SDK comes back as `UnknownJob`.

        Narrow with isinstance to read what only one status has, such as
        `output` on `JobComplete` and `error` on `JobFailed`.
        """
        return self._get(job_id, None)

    def _get(self, job_id: str, deadline: Optional[float]) -> SomeJob:
        safe = path_segment("job_id", job_id)
        return self._job("GET", f"/jobs/{safe}", lambda: self._raw.get_job(safe), deadline)

    def list(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page.

        `limit` is the page size (1 or more, the API sets the maximum) and `offset` the jobs to skip.
        """
        page_window(limit, offset)
        list_filters(status, type)
        try:
            res = self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        except ResponseValidationError as err:
            return job_page(err)
        jobs: List[SomeJob] = list(res.data)
        return Page(jobs, res.meta)

    def list_all(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, page_size: int = 100) -> Iterator[SomeJob]:
        """Every matching job, fetching pages as you iterate."""
        page_window(page_size, None)
        offset = 0
        while True:
            page = self.list(status=status, type=type, limit=page_size, offset=offset)
            yield from page.data
            offset += len(page.data)
            if not page.data or offset >= page.meta.total:
                return

    def cancel(self, job_id: str) -> Union[JobCancellation, UnknownJob]:
        """Cancel a job that has not finished."""
        safe = path_segment("job_id", job_id)
        return self._job("POST", f"/jobs/{safe}/cancel", lambda: self._raw.cancel_job(safe))

    def download(self, job_id: str, to: DownloadTarget) -> int:
        """Stream a completed job's output file to `to` and return the bytes written.

        `to` is a file path (created or replaced) or a binary file you opened
        (`open(path, "wb")`, `io.BytesIO()`). The body is never held in memory.
        A failure before the body starts is retried like any call. One after it
        started is raised at once, and a file this call created is removed.
        """
        safe = path_segment("job_id", job_id)

        def fetch() -> _Fetched[int]:
            with self._raw.download_job_output(safe) as response:
                sink = Sink(to)
                try:
                    for chunk in response.data:
                        sink.write(chunk)
                except BaseException as err:
                    sink.fail()
                    raise body_failed(err) from err
                return _Fetched(response.headers, sink.finish())

        return self._client._call("GET", f"/jobs/{safe}/download", fetch)

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
                ends the wait. A status newer than this SDK counts as not
                finished, so it too ends at this bound.
            interval: Seconds before the second poll. Each later pause is 1.5 times longer.
            max_interval: The longest pause between polls, in seconds.
            on_progress: Called with the job after every poll.
            throw_on_failure: Raise `JobFailedError` when the job fails or is
                cancelled. Default: return that job instead.
        """
        wait_options(timeout, interval, max_interval)
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval, throw_on_failure=throw_on_failure)
        while True:
            job = self._get(job_id, poll.clock.deadline)
            if on_progress is not None:
                on_progress(job)
            done = poll.finished(job)
            if done is not None:
                return done
            time.sleep(poll.pause(job))

    @overload
    def run(self, job: Union[SubmitJob, UntypedJob], *,
            idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[List[str]] = None,
            callback: Optional[Callback] = None, force_async: Optional[bool] = None,
            timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
            on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True] = True) -> JobComplete: ...

    @overload
    def run(self, job: Union[SubmitJob, UntypedJob], *,
            idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[List[str]] = None,
            callback: Optional[Callback] = None, force_async: Optional[bool] = None,
            timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
            on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool) -> FinishedJob: ...

    def run(
        self,
        job: Union[SubmitJob, UntypedJob],
        *,
        idempotency_key: Optional[str] = None,
        label: Optional[str] = None,
        destinations: Optional[List[str]] = None,
        callback: Optional[Callback] = None,
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
            job: What to run, typed per job type (see `jobs.create()`), or an `UntypedJob`.
            idempotency_key: Makes the submit safe to repeat (see `jobs.create()`).
                Reusing a key with different params raises `ConflictError` (409).
            label: A short name for the job, shown in the dashboard.
            destinations: Where to deliver the output, as a list of `storage://<id>[/<folder or path>]`.
            callback: A URL Rendobar POSTs the job to when it ends (see `jobs.create()`).
            force_async: Queue the job even when its type can finish during the request.
            timeout: Seconds to wait (see `jobs.wait()`). Default: five minutes,
                extended to the job's own execution budget once it reports one.
            interval: Seconds before the second poll. Each later pause is 1.5 times longer.
            max_interval: The longest pause between polls, in seconds.
            on_progress: Called with the job after every poll.
            throw_on_failure: Raise `JobFailedError` when the job fails or is cancelled. Default: True.
        """
        wait_options(timeout, interval, max_interval)
        created = self.create(job, idempotency_key=idempotency_key, label=label, destinations=destinations,
                              callback=callback, force_async=force_async)
        return self.wait(created.id, timeout=timeout, interval=interval, max_interval=max_interval,
                         on_progress=on_progress, throw_on_failure=throw_on_failure)


class Account:
    """What this API key's workspace may do."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client

    def capabilities(self) -> AccountCapabilities:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        capabilities: AccountCapabilities = self._client._call("GET", "/account/capabilities", raw.get_account_capabilities).data
        return capabilities

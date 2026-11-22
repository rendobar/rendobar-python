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
    Iterator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_type_hints,
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
from ._generated.core.request_options import RequestOptions
from ._generated.core.serialization import convert_and_respect_annotation_metadata
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
from ._plumbing import (
    Envelope,
    Fetched,
    Page,
    Reader,
    Response,
    Sent,
    one,
    listed,
    page_window,
    path_segment,
    text,
    whole,
)
from ._resource_models import DeliveriesRetried, JobLogEntry, JobSort, JobStats, JobTimings, SortOrder, StatsWindow
from ._resources import (
    ApiKeys,
    Assets,
    Billing,
    Compose,
    Notifications,
    Orgs,
    Storage,
    Uploads,
    Webhooks,
)
from ._realtime import Realtime
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


def _variants() -> Dict[str, Type[object]]:
    """Each typed job's TypedDict by its `type`, read from the generated union so a new job type needs no edit."""
    out: Dict[str, Type[object]] = {}
    for variant in get_args(SubmitJob):
        kinds = get_args(get_type_hints(variant)["type"])
        out[str(kinds[0])] = variant
    return out


_VARIANTS = _variants()


def submit_body(
    job: Union[SubmitJob, UntypedJob],
    *,
    idempotency_key: str,
    label: Optional[str],
    destinations: Optional[List[str]],
    callback: Optional[Callback],
    force_async: Optional[bool],
) -> Dict[str, object]:
    """The submit body exactly as sent, in the API's field names.

    A typed job is serialised by its own job type's TypedDict (snake_case keys
    to the wire's camelCase). An UntypedJob's params and inputs go as given:
    the SDK knows nothing about them, so it renames nothing. `idempotency_key`
    is the caller's, or one `generate_idempotency_key()` made for this call.
    """
    if isinstance(job, UntypedJob):
        body = _job_fields({"type": job.type, "params": job.params, "inputs": job.inputs})
    else:
        fields = _job_fields(job)
        variant = _VARIANTS.get(str(fields["type"]))
        if variant is None:
            raise InvalidArgumentError(f"{fields['type']!r} is not a job type this SDK types. Submit it as UntypedJob({fields['type']!r}, params).")
        converted: object = convert_and_respect_annotation_metadata(object_=fields, annotation=variant, direction="write")
        body = _job_fields(converted)
    body["idempotencyKey"] = idempotency_key
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
        body["forceAsync"] = force_async
    return body


# The core's submit_job serialises its `request` through the whole submit union, which renames
# any key that matches a field of any job type. The SDK sends its own body instead, as the
# request's extra body parameters, over an empty request that the union leaves empty.
_EMPTY_REQUEST = cast(SubmitJobRequestParams, {})  # an empty dict serialises to nothing; it is never read


def status_filter(status: Optional[str]) -> RequestOptions:
    """The `status` filter of jobs.list(), sent as a query parameter of its own so a status newer than this SDK passes too."""
    return RequestOptions(additional_query_parameters={"status": status}) if status is not None else RequestOptions()


def submit_options(body: Dict[str, object]) -> RequestOptions:
    return RequestOptions(additional_body_parameters=body)


def job_filters(client: Optional[str], from_: Optional[int], to: Optional[int]) -> None:
    """InvalidArgumentError for a jobs.list() client filter that is not a string, or a time that is not a whole number."""
    text("client", client)
    whole("from_", from_, 0)
    whole("to", to, 0)


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

    Unknown fields are kept. An optional field holding a variant newer than
    this SDK (such as an ffprobe summary of a new `kind`) is read as None, and
    its value is kept in `result.model_extra["unknown_<field>"]`, so the rest of
    the result stays typed. Raises ResponseValidationError when the data is
    not that shape at all (such as a result type of another job type).
    """
    data = job.output.data
    try:
        return model.model_validate(data)
    except pydantic.ValidationError as err:
        fields = as_mapping(data)
        newer = _newer_variants(err, model)
        if fields is not None and newer:
            kept = {key: value for key, value in fields.items() if key not in newer}
            kept.update({f"unknown_{key}": fields[key] for key in newer})
            try:
                return model.model_validate(kept)
            except pydantic.ValidationError:
                pass
        raise ResponseValidationError(
            f"Job {job.id} ({job.type}) has output data that is not a {model.__name__}.",
            status_code=None, body=data,
        ) from None


def _newer_variants(err: pydantic.ValidationError, model: Type[pydantic.BaseModel]) -> Set[str]:
    """The optional top-level fields that failed only because their union variant is unknown to this SDK."""
    optional = {field.alias or name for name, field in model.model_fields.items() if not field.is_required()}
    failed: Dict[str, Set[str]] = {}
    for problem in err.errors():
        where = problem["loc"]
        if where and isinstance(where[0], str):
            failed.setdefault(where[0], set()).add(problem["type"] if len(where) == 1 else "nested")
    return {key for key, kinds in failed.items() if kinds == {"union_tag_invalid"} and key in optional}


def one_job(err: ResponseValidationError) -> UnknownJob:
    """Recovers a single-job response (get, create, cancel) the core could not parse."""
    body = as_mapping(err.body)
    data = as_mapping(body.get("data")) if body is not None else None
    if data is not None and _is_newer_job(data):
        return UnknownJob(data)
    raise err


_META_ADAPTER: pydantic.TypeAdapter[PageMeta] = pydantic.TypeAdapter(PageMeta)


def job_page(err: ResponseValidationError) -> Page[SomeJob, PageMeta]:
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
                replayable: bool = True, clock: Callable[[], float] = time.monotonic,
                rand: Callable[[], float] = random.random) -> Optional[float]:
    """Seconds to wait before retry number `attempt + 1`, or None to raise now.

    `deadline` (on `clock`, monotonic seconds) is the caller's: a retry that
    would sleep past it is not made, and the error raises at once.

    Retried: 429, 500, 502, 503 and 504 (after `Retry-After` when sent, else
    exponential backoff with jitter) and connection failures where the request
    never reached the API. Never retried: any other status (a 409 conflict, a
    501, a 408), a read timeout (the API may still be working on it), and a
    response this SDK cannot read. A request that is not `replayable` (a write
    that is not keyed, such as creating a webhook endpoint) is retried only
    after a 429 or a connection that was never made: after a 5xx it may have
    taken effect, and repeating it could do it twice.
    """
    if attempt >= max_retries:
        return None
    err = normalize(err)
    if isinstance(err, _GeneratedApiError):
        if err.status_code not in RETRIED_STATUSES or (not replayable and err.status_code != 429):
            return None
        headers = {k.lower(): v for k, v in (err.headers or {}).items()}
        after = parse_retry_after(headers.get("retry-after"))
        if after is not None:
            return _within(after if after <= _MAX_RETRY_AFTER else None, deadline, clock)
    elif not isinstance(err, (httpx.ConnectError, httpx.ConnectTimeout)):
        return None
    backoff = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)
    return _within(backoff * (0.75 + 0.5 * rand()), deadline, clock)


def is_read(method: str) -> bool:
    """A method that changes nothing, so repeating it after a 5xx is safe."""
    return method in ("GET", "HEAD")


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
        options = core_options(self._api_key, base_url=base_url, timeout=timeout, app=app)
        self._base_url = base_url
        self._headers = options["headers"]  # X-Rendobar-Client, for the event stream's handshake too
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)  # owned here, so close() needs no core internals
        self._core = GeneratedClient(**options, httpx_client=self._http)
        self._max_retries = max_retries
        self._closed = False
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = Jobs(self)
        self.account = Account(self)
        self.billing = Billing(self)
        self.uploads = Uploads(self)
        self.assets = Assets(self)
        self.webhooks = Webhooks(self)
        self.storage = Storage(self)
        self.api_keys = ApiKeys(self)
        self.orgs = Orgs(self)
        self.compose = Compose(self)
        self.notifications = Notifications(self)
        self.realtime = Realtime(self)

    def close(self) -> None:
        """Close the underlying HTTP connections. Every call after raises RendobarError (code `CLIENT_CLOSED`)."""
        self._closed = True
        self._http.close()

    def __enter__(self) -> Rendobar:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        self.close()

    # ── shared plumbing ──────────────────────────────────────────────

    def _call(self, method: str, path: str, fn: Callable[[], Response[T]], *, public: bool = False,
              deadline: Optional[float] = None, replayable: Optional[bool] = None) -> T:
        """One API call: retried per `retry_delay`, failures raised as RendobarError, deprecation noted.

        A call that needs a key (every one but `public`) raises at once when the client has none.
        No retry sleeps past `deadline` (time.monotonic seconds). `replayable` defaults to
        whether the method is a read (GET); a keyed submit and a cancel say so themselves.
        """
        if self._closed:
            raise client_closed()
        if not public:
            require_key(self._api_key)
        safe = replayable if replayable is not None else is_read(method)
        attempt = 0
        while True:
            try:
                response = fn()
            except _CORE_FAILURES as err:
                delay = retry_delay(err, attempt, self._max_retries, deadline=deadline, replayable=safe)
                if delay is None:
                    raise to_public(err) from err
                attempt += 1
                time.sleep(delay)
                continue
            self._deprecations.note(response, method, path)
            return response.data

    def _read(self, method: str, path: str, call: Callable[[], Sent], read: Reader[T], *, replayable: Optional[bool] = None) -> T:
        """`_call` for a generated core call whose answer `read` parses into the public model."""
        def fetch() -> Fetched[T]:
            sent = call()
            return Fetched(sent.headers, read(sent.response))

        return self._call(method, path, fetch, replayable=replayable)


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
            return self._client._call(method, path, fn, deadline=deadline, replayable=True).data
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
        def submit() -> Fetched[Submitted]:
            sent = self._raw.submit_job(request=_EMPTY_REQUEST, request_options=submit_options(request))
            return Fetched(sent.headers, submitted(sent.response))

        try:
            return self._client._call("POST", "/jobs", submit, replayable=True)  # keyed: a repeat replays the first job
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

    def list(
        self,
        *,
        status: Union[JobStatus, str, None] = None,
        type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort: Optional[JobSort] = None,
        order: Optional[SortOrder] = None,
        client: Optional[str] = None,
        from_: Optional[int] = None,
        to: Optional[int] = None,
    ) -> Page[SomeJob, PageMeta]:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page.

        Args:
            status: Only jobs in this status.
            type: Only jobs of this job type.
            limit: The page size (1 or more, the API sets the maximum).
            offset: The jobs to skip.
            sort: `"created"` (default), `"duration"` or `"cost"`.
            order: `"desc"` (default) or `"asc"`.
            client: Only jobs submitted from this client, such as `"python"`, `"cli"` or `"dashboard"`.
            from_: Only jobs created at or after this time, in Unix milliseconds.
            to: Only jobs created at or before this time, in Unix milliseconds.
        """
        page_window(limit, offset)
        list_filters(status, type)
        job_filters(client, from_, to)
        try:
            res = self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(
                type=type, limit=limit, offset=offset, sort=sort, order=order, client=client, from_=from_, to=to,
                request_options=status_filter(status)))
        except ResponseValidationError as err:
            return job_page(err)
        jobs: List[SomeJob] = list(res.data)
        return Page(jobs, res.meta)

    def list_all(
        self,
        *,
        status: Union[JobStatus, str, None] = None,
        type: Optional[str] = None,
        sort: Optional[JobSort] = None,
        order: Optional[SortOrder] = None,
        client: Optional[str] = None,
        from_: Optional[int] = None,
        to: Optional[int] = None,
        page_size: int = 100,
    ) -> Iterator[SomeJob]:
        """Every matching job, fetching pages of `page_size` as you iterate. Takes the filters of `list()`."""
        page_window(page_size, None)
        offset = 0
        while True:
            page = self.list(status=status, type=type, sort=sort, order=order, client=client, from_=from_, to=to,
                             limit=page_size, offset=offset)
            yield from page.data
            offset += len(page.data)
            if not page.data or offset >= page.meta.total:
                return

    def cancel(self, job_id: str) -> Union[JobCancellation, UnknownJob]:
        """Cancel a job that has not finished."""
        safe = path_segment("job_id", job_id)
        return self._job("POST", f"/jobs/{safe}/cancel", lambda: self._raw.cancel_job(safe))

    def retry_deliveries(self, job_id: str) -> DeliveriesRetried:
        """Put a completed job's failed storage deliveries back on the queue. `retried` says how many."""
        safe = path_segment("job_id", job_id)
        return self._client._read("POST", f"/jobs/{safe}/deliveries/retry", lambda: self._raw.retry_deliveries(safe),
                                  one(DeliveriesRetried))

    def logs(self, job_id: str) -> List[JobLogEntry]:
        """The job's log lines, oldest first: `timestamp` (Unix ms), `level`, `event`, `message` and the `step` it came from."""
        safe = path_segment("job_id", job_id)
        return self._client._read("GET", f"/jobs/{safe}/logs", lambda: self._raw.get_job_logs(safe), listed(JobLogEntry))

    def get_timings(self, job_id: str) -> JobTimings:
        """Where the job's time went, in milliseconds: the API's checks, the queue, download, execute and upload."""
        safe = path_segment("job_id", job_id)
        return self._client._read("GET", f"/jobs/{safe}/timings", lambda: self._raw.get_job_timings(safe), one(JobTimings))

    def stats(self, *, window: Optional[StatsWindow] = None) -> JobStats:
        """Totals, success rate, average duration and spend over `window` (default `"24h"`; `"all"` is the workspace's whole history)."""
        return self._client._read("GET", "/jobs/stats", lambda: self._raw.get_job_stats(window=window), one(JobStats))

    def download(self, job_id: str, to: DownloadTarget) -> int:
        """Stream a completed job's output file to `to` and return the bytes written.

        `to` is a file path (created or replaced) or a binary file you opened
        (`open(path, "wb")`, `io.BytesIO()`). The body is never held in memory.
        A failure before the body starts is retried like any call. One after it
        started is raised at once, and a file this call created is removed.
        """
        safe = path_segment("job_id", job_id)

        def fetch() -> Fetched[int]:
            with self._raw.download_job_output(safe) as response:
                sink = Sink(to)
                try:
                    for chunk in response.data:
                        sink.write(chunk)
                except BaseException as err:
                    sink.fail()
                    raise body_failed(err) from err
                return Fetched(response.headers, sink.finish())

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
                ends the wait. A status newer than this SDK ends the wait,
                returned as an UnknownJob, when the job reports it is
                `terminal`, and is polled until this bound when it is not.
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

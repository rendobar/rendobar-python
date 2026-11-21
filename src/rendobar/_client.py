"""The Rendobar client.

A thin, hand-written layer over the generated core in `_generated` (Fern, from
the published OpenAPI document). The core supplies models, retries with
`Retry-After`, timeouts and HTTP. This layer adds what a spec cannot say:

- the same method names as `@rendobar/sdk` (`jobs.create`, `jobs.run`, ...),
- responses unwrapped from the `{data}` envelope,
- one idempotency key per `jobs.create()` call, so a retried submit cannot
  create a second job,
- `jobs.wait()` / `jobs.run()`, `jobs.list_all()`,
- `RENDOBAR_API_KEY` from the environment, the `X-Rendobar-Client` header,
- `Deprecation` notices, and a job whose status is newer than this SDK.

Behaviour is held to the shared conformance scenarios (tests/test_conformance.py).
"""
from __future__ import annotations

import datetime as _dt
import os
import platform
import re
import secrets
import time
import warnings
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence

from ._errors import JobFailedError, WaitTimeoutError, from_generated
from ._generated.client import GeneratedClient
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError
from ._generated.types.submit_any_job import SubmitAnyJob
from ._version import __version__

DEFAULT_BASE_URL = "https://api.rendobar.com"
TERMINAL_STATUSES = frozenset({"complete", "failed", "cancelled"})
_DEFAULT_WAIT_TIMEOUT = 300.0  # seconds, until the job reports its own budget
_WAIT_GRACE = 120.0  # headroom past the job's budget for upload and callback
_APP_NAME = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")


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
            warnings.warn(f"[rendobar] {key} is deprecated since {since.date()}. It keeps working until the next major release.", DeprecationWarning, stacklevel=5)
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


def unknown_job_or_raise(err: ParsingError) -> UnknownJob:
    """A job the core could not parse because its status is newer than this SDK."""
    data = err.body.get("data") if isinstance(err.body, Mapping) else None
    if isinstance(data, Mapping):
        return UnknownJob(data)
    raise err


class WaitClock:
    """The deadline of jobs.wait(): five minutes until the job reports its own budget, then that plus grace."""

    def __init__(self, timeout: Optional[float]) -> None:
        self.explicit = timeout is not None
        self.started = time.monotonic()
        self.deadline = self.started + (timeout if timeout is not None else _DEFAULT_WAIT_TIMEOUT)
        self.adopted = False

    def observe(self, job: Any) -> None:
        budget_ms = getattr(job, "timeout_ms", None)
        if not self.explicit and not self.adopted and isinstance(budget_ms, (int, float)):
            self.adopted = True
            self.deadline = max(self.deadline, self.started + budget_ms / 1000 + _WAIT_GRACE)

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def total(self) -> float:
        return self.deadline - self.started


class Rendobar:
    """The Rendobar API client.

    >>> from rendobar import Rendobar
    >>> rb = Rendobar()  # reads RENDOBAR_API_KEY
    >>> job = rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})
    >>> job.status
    'complete'
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
        if app is not None and not _APP_NAME.match(app):
            raise ValueError('"app" must be 1-32 letters, digits or . _ + -')
        key = api_key if api_key is not None else (os.environ.get("RENDOBAR_API_KEY") or None)
        self._core = GeneratedClient(
            base_url=base_url,
            token=key,
            headers={"X-Rendobar-Client": _client_header(app)},
            timeout=timeout,
            max_retries=max_retries,
        )
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = Jobs(self)
        self.account = Account(self)

    # ── shared plumbing ──────────────────────────────────────────────

    def _note(self, response: Any, method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    def _call(self, method: str, path: str, fn: Callable[[], Any]) -> Any:
        try:
            response = fn()
        except _GeneratedApiError as err:
            raise from_generated(err) from err
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
        return self._client._call("POST", "/jobs", lambda: self._raw.submit_job(request=request)).data

    def get(self, job_id: str) -> Any:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        try:
            return self._client._call("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(job_id)).data
        except ParsingError as err:
            return unknown_job_or_raise(err)

    def list(self, *, status: Optional[str] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first."""
        res = self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
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
        return self._client._call("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(job_id)).data

    def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        try:
            with self._raw.download_job_output(job_id) as response:
                self._client._note(response, "GET", f"/jobs/{job_id}/download")
                return b"".join(response.data)
        except _GeneratedApiError as err:
            raise from_generated(err) from err

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

        With no `timeout`, the wait follows the job's own execution budget (its
        `timeout_ms`, your plan's per-job limit) plus two minutes for upload and
        delivery, so a long job is not reported as timed out while it runs.
        Until the server reports that budget, the bound is five minutes.
        """
        clock = WaitClock(timeout)
        delay = interval
        while True:
            job = self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            if job.status in TERMINAL_STATUSES:
                if throw_on_failure and job.status != "complete":
                    raise JobFailedError(job)
                return job
            clock.observe(job)
            if clock.remaining() <= 0:
                raise WaitTimeoutError(job_id, job.status, clock.total())
            time.sleep(min(delay, clock.remaining()))
            delay = min(delay * 1.5, max_interval)

    def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *, throw_on_failure: bool = True, **options: Any) -> Any:
        """Submit a job and wait for it. Raises `JobFailedError` if it fails, unless `throw_on_failure=False`."""
        wait_keys = {"timeout", "interval", "max_interval", "on_progress"}
        created = self.create(type, params, inputs, **{k: v for k, v in options.items() if k not in wait_keys})
        return self.wait(created.id, throw_on_failure=throw_on_failure, **{k: v for k, v in options.items() if k in wait_keys})


class Account:
    """What this API key's workspace may do."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client

    def capabilities(self) -> Any:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return self._client._call("GET", "/account/capabilities", raw.get_account_capabilities).data

"""Errors raised by the Rendobar client.

Everything this SDK raises is a `RendobarError` subclass carrying a
machine-readable `code`. An error response from the API also carries the HTTP
`status_code` and the `request_id` to quote to support. Catch the subclass for
the case you handle, or `RendobarError` for all of them.

    RendobarError
    ├── BadRequestError (400), AuthenticationError (401), InsufficientCreditsError (402),
    │   PermissionDeniedError (403), NotFoundError (404), ConflictError (409),
    │   RateLimitError (429), InternalServerError (5xx)
    ├── InvalidArgumentError        a bad argument, caught before any request (also a ValueError)
    ├── APIConnectionError          the request did not get a response
    │   └── APITimeoutError         it timed out
    ├── ResponseValidationError     a response this SDK version cannot read
    ├── JobFailedError              a waited-on job ended failed or cancelled
    └── WaitTimeoutError            jobs.wait() gave up; the job may still finish
"""
from __future__ import annotations

import email.utils
import time
from typing import Any, Dict, Mapping, Optional, Type, Union

import httpx

from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError as _GeneratedParsingError
from ._models import JobCancelled, JobFailed

REQUEST_ID_HEADER = "x-request-id"


class RendobarError(Exception):
    """The base of every error this SDK raises. `status_code` is None when no HTTP response was involved."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        details: Any = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details
        self.retry_after = retry_after

    def __str__(self) -> str:
        rid = f" (request {self.request_id})" if self.request_id else ""
        return f"{self.code}: {self.message}{rid}"


class BadRequestError(RendobarError):
    """400: the request was invalid. `details` lists the problems."""


class AuthenticationError(RendobarError):
    """401: invalid or expired API key.

    Also raised before any request, with `status_code` None, when the client
    has no key (code `MISSING_API_KEY`) or a key that is not a Rendobar key
    (code `INVALID_API_KEY`): see `api_key_error`.
    """


class InsufficientCreditsError(RendobarError):
    """402: the balance cannot cover the job."""


class PermissionDeniedError(RendobarError):
    """403: the key lacks a scope, or the plan does not allow this."""


class NotFoundError(RendobarError):
    """404: no such resource in this workspace."""


class ConflictError(RendobarError):
    """409: conflicts with the current state, such as a reused idempotency key."""


class RateLimitError(RendobarError):
    """429: too many requests. `retry_after` is the wait in seconds."""


class InternalServerError(RendobarError):
    """5xx: a failure on Rendobar's side. Safe to retry."""


_BY_STATUS: Dict[int, Type[RendobarError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: InsufficientCreditsError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
}


def api_key_error(key: Optional[str]) -> Optional[AuthenticationError]:
    """Why `key` cannot authenticate, found before anything is sent: missing or blank, or not a Rendobar key. None when it may.

    Every Rendobar API key starts with `rb_`, so anything else would only earn the API's 401.
    """
    if key is None or not key.strip():
        return AuthenticationError(
            "No API key. Pass Rendobar(api_key=...) or set the RENDOBAR_API_KEY environment variable.",
            code="MISSING_API_KEY",
        )
    if not key.startswith("rb_"):
        return AuthenticationError(
            "This is not a Rendobar API key: keys start with rb_. Check the api_key you passed or RENDOBAR_API_KEY.",
            code="INVALID_API_KEY",
        )
    return None


class InvalidArgumentError(RendobarError, ValueError):
    """An argument the SDK refuses before sending any request, such as a job id with a `/` in it or `limit=0`.

    `code` is `INVALID_ARGUMENT`. Also a ValueError, so code that catches ValueError keeps working.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INVALID_ARGUMENT")


class APIConnectionError(RendobarError):
    """The request got no response: the connection failed or dropped. Connection failures are retried first."""

    def __init__(self, message: str = "Could not reach the Rendobar API", *, code: str = "CONNECTION_ERROR") -> None:
        super().__init__(message, code=code)


class APITimeoutError(APIConnectionError):
    """The request timed out (the client's `timeout`)."""

    def __init__(self, message: str = "The request to the Rendobar API timed out") -> None:
        super().__init__(message, code="TIMEOUT")


class ResponseValidationError(RendobarError):
    """The API answered with a body this SDK version cannot read. `body` holds it as sent."""

    def __init__(self, message: str, *, status_code: Optional[int], body: Any, headers: Optional[Mapping[str, str]] = None) -> None:
        lowered = {k.lower(): v for k, v in (headers or {}).items()}
        super().__init__(message, code="INVALID_RESPONSE", status_code=status_code, request_id=lowered.get(REQUEST_ID_HEADER))
        self.body = body


class JobFailedError(RendobarError):
    """Raised by `jobs.wait(throw_on_failure=True)` and `jobs.run()` when a job ends failed or cancelled.

    `code` is the job's own error code (`JOB_CANCELLED` for a cancelled job), `job` the job itself.
    """

    def __init__(self, job: Union[JobFailed, JobCancelled]) -> None:
        if isinstance(job, JobFailed):
            code, detail = job.error.code or "JOB_FAILED", job.error.message
        else:
            code, detail = "JOB_CANCELLED", ""
        super().__init__(f"Job {job.id} ended with status {job.status!r}" + (f": {detail}" if detail else "."), code=code)
        self.job: Union[JobFailed, JobCancelled] = job
        self.job_id: str = job.id
        self.status: str = job.status

    def __str__(self) -> str:
        return self.message


class WaitTimeoutError(RendobarError):
    """Raised by `jobs.wait()` when the deadline passes before the job ends. The job may still finish."""

    def __init__(self, job_id: str, last_status: str, timeout: float) -> None:
        super().__init__(
            f"Job {job_id} did not finish within {format_seconds(timeout)} (last status: {last_status}). It may still complete.",
            code="WAIT_TIMEOUT",
        )
        self.job_id = job_id
        self.last_status = last_status
        self.timeout = timeout

    def __str__(self) -> str:
        return self.message


def format_seconds(seconds: float) -> str:
    """`0.5` -> "0.5s", `2.0` -> "2s", `420.4` -> "420s": whole seconds from 10 up, three significant digits below."""
    return f"{seconds:.0f}s" if seconds >= 10 else f"{seconds:.3g}s"


def parse_retry_after(value: Optional[str], *, now: Optional[float] = None) -> Optional[float]:
    """`Retry-After` as seconds: delta-seconds or an HTTP date. None when absent or unreadable."""
    if value is None:
        return None
    text = value.strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    return max(0.0, when.timestamp() - (time.time() if now is None else now))


def _field(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def from_generated(err: _GeneratedApiError) -> RendobarError:
    """Turns the generated core's ApiError into the public RendobarError hierarchy."""
    status = err.status_code or 0
    body = err.body
    envelope = _field(body, "error")
    code = _field(envelope, "code") or "UNKNOWN_ERROR"
    message = _field(envelope, "message") or f"Request failed with status {status}"
    headers = {k.lower(): v for k, v in (err.headers or {}).items()}
    retry_after = parse_retry_after(headers.get("retry-after"))
    cls = _BY_STATUS.get(status) or (InternalServerError if status >= 500 else RendobarError)
    out = cls(
        str(message),
        code=str(code),
        status_code=status,
        request_id=headers.get(REQUEST_ID_HEADER),
        details=_field(envelope, "details"),
        retry_after=retry_after,
    )
    out.__cause__ = err
    return out


def from_parsing(err: _GeneratedParsingError) -> ResponseValidationError:
    out = ResponseValidationError(
        "The API response does not match this SDK version. Upgrade rendobar, or read `body`.",
        status_code=err.status_code,
        body=err.body,
        headers=err.headers,
    )
    out.__cause__ = err
    return out


def normalize(err: BaseException) -> BaseException:
    """An error response whose body the core could not read is still that status's error, not a parse failure."""
    if isinstance(err, _GeneratedParsingError) and err.status_code is not None and not 200 <= err.status_code < 300:
        out = _GeneratedApiError(status_code=err.status_code, headers=err.headers, body=err.body)
        out.__cause__ = err
        return out
    return err


def to_public(err: BaseException) -> RendobarError:
    """Any failure from the generated core or the transport, as a RendobarError."""
    if isinstance(err, RendobarError):
        return err
    err = normalize(err)
    if isinstance(err, _GeneratedApiError):
        return from_generated(err)
    if isinstance(err, _GeneratedParsingError):
        return from_parsing(err)
    if isinstance(err, httpx.TimeoutException):
        out: RendobarError = APITimeoutError(f"The request to the Rendobar API timed out ({type(err).__name__})")
    elif isinstance(err, httpx.TransportError):
        detail = str(err) or type(err).__name__
        out = APIConnectionError(f"Could not reach the Rendobar API: {detail}")
    else:
        raise TypeError(f"not a transport or API failure: {err!r}")
    out.__cause__ = err
    return out

"""Errors raised by the Rendobar client.

Every failed API call raises a `RendobarError` subclass carrying the API's
machine-readable `code`, the HTTP `status_code`, and the `request_id` to quote
to support. Catch the subclass for the case you handle, or `RendobarError`
for all of them.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Type

from ._generated.core.api_error import ApiError as _GeneratedApiError

REQUEST_ID_HEADER = "x-request-id"


class RendobarError(Exception):
    """An error response from the Rendobar API."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
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
    """401: missing, invalid or expired API key."""


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


class JobFailedError(Exception):
    """Raised by `jobs.wait(throw_on_failure=True)` and `jobs.run()` when a job ends failed or cancelled."""

    def __init__(self, job: Any) -> None:
        detail = getattr(getattr(job, "error", None), "message", None)
        super().__init__(f"Job {job.id} ended with status {job.status!r}" + (f": {detail}" if detail else "."))
        self.job = job
        self.job_id = job.id
        self.status = job.status


class WaitTimeoutError(Exception):
    """Raised by `jobs.wait()` when the deadline passes before the job ends. The job may still finish."""

    def __init__(self, job_id: str, last_status: str, timeout: float) -> None:
        super().__init__(f"Job {job_id} did not finish within {timeout:.0f}s (last status: {last_status}). It may still complete.")
        self.job_id = job_id
        self.last_status = last_status
        self.timeout = timeout


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
    retry_after: Optional[float] = None
    if "retry-after" in headers:
        try:
            retry_after = float(headers["retry-after"])
        except ValueError:
            retry_after = None
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

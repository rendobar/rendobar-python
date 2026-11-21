"""The asyncio Rendobar client: the same methods as `Rendobar`, awaited.

Body building, the unknown-status fallback, deprecation notices and the wait
deadline are shared with the sync client (`_client`), so the two cannot drift.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator, Awaitable, Callable, List, Mapping, Optional, Sequence

from ._client import (
    _APP_NAME,
    DEFAULT_BASE_URL,
    TERMINAL_STATUSES,
    DeprecationNotice,
    Page,
    _Deprecations,
    WaitClock,
    _client_header,
    build_submit,
    unknown_job_or_raise,
)
from ._errors import JobFailedError, WaitTimeoutError, from_generated
from ._generated.client import AsyncGeneratedClient
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._generated.core.parse_error import ParsingError


class AsyncRendobar:
    """The Rendobar API client for asyncio.

    >>> rb = AsyncRendobar()  # reads RENDOBAR_API_KEY
    >>> job = await rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})
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
        self._core = AsyncGeneratedClient(
            base_url=base_url,
            token=key,
            headers={"X-Rendobar-Client": _client_header(app)},
            timeout=timeout,
            max_retries=max_retries,
        )
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = AsyncJobs(self)
        self.account = AsyncAccount(self)

    def _note(self, response: Any, method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    async def _call(self, method: str, path: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        try:
            response = await fn()
        except _GeneratedApiError as err:
            raise from_generated(err) from err
        self._note(response, method, path)
        return response.data


class AsyncJobs:
    """Submit jobs, follow them to the end, and read their output."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.jobs.with_raw_response

    async def types(self) -> List[Any]:
        """Every live job type. Public: needs no API key."""
        return list((await self._client._call("GET", "/jobs/types", self._raw.list_job_types)).data)

    async def create(
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
        """Submit a job. Safe to retry: a generated key rides every retry of this call."""
        request = build_submit(type, params, inputs, idempotency_key=idempotency_key, label=label,
                               destinations=destinations, callback=callback, force_async=force_async)
        return (await self._client._call("POST", "/jobs", lambda: self._raw.submit_job(request=request))).data

    async def get(self, job_id: str) -> Any:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        try:
            return (await self._client._call("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(job_id))).data
        except ParsingError as err:
            return unknown_job_or_raise(err)

    async def list(self, *, status: Optional[str] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first."""
        res = await self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        return Page(list(res.data), res.meta)

    async def list_all(self, *, status: Optional[str] = None, type: Optional[str] = None, page_size: int = 100) -> AsyncIterator[Any]:
        """Every matching job, fetching pages as you iterate."""
        offset = 0
        while True:
            page = await self.list(status=status, type=type, limit=page_size, offset=offset)
            for job in page.data:
                yield job
            offset += len(page.data)
            total = getattr(page.meta, "total", None)
            if not page.data or (total is not None and offset >= total):
                return

    async def cancel(self, job_id: str) -> Any:
        """Cancel a job that has not finished."""
        return (await self._client._call("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(job_id))).data

    async def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        try:
            async with self._raw.download_job_output(job_id) as response:
                self._client._note(response, "GET", f"/jobs/{job_id}/download")
                return b"".join([chunk async for chunk in response.data])
        except _GeneratedApiError as err:
            raise from_generated(err) from err

    async def wait(
        self,
        job_id: str,
        *,
        timeout: Optional[float] = None,
        interval: float = 2.0,
        max_interval: float = 10.0,
        on_progress: Optional[Callable[[Any], None]] = None,
        throw_on_failure: bool = False,
    ) -> Any:
        """Poll until the job ends. Same deadline rules as `Rendobar.jobs.wait`."""
        clock = WaitClock(timeout)
        delay = interval
        while True:
            job = await self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            if job.status in TERMINAL_STATUSES:
                if throw_on_failure and job.status != "complete":
                    raise JobFailedError(job)
                return job
            clock.observe(job)
            if clock.remaining() <= 0:
                raise WaitTimeoutError(job_id, job.status, clock.total())
            await asyncio.sleep(min(delay, clock.remaining()))
            delay = min(delay * 1.5, max_interval)

    async def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *, throw_on_failure: bool = True, **options: Any) -> Any:
        """Submit a job and wait for it. Raises `JobFailedError` if it fails, unless `throw_on_failure=False`."""
        wait_keys = {"timeout", "interval", "max_interval", "on_progress"}
        created = await self.create(type, params, inputs, **{k: v for k, v in options.items() if k not in wait_keys})
        return await self.wait(created.id, throw_on_failure=throw_on_failure, **{k: v for k, v in options.items() if k in wait_keys})


class AsyncAccount:
    """What this API key's workspace may do."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client

    async def capabilities(self) -> Any:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return (await self._client._call("GET", "/account/capabilities", raw.get_account_capabilities)).data

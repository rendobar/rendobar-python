"""The asyncio Rendobar client: the same methods as `Rendobar`, awaited.

Everything that is not I/O is shared with the sync client (`_client`): the core
options, the retry decision, body building, the unknown-status fallback,
deprecation notices and the wait poll. This file only awaits and sleeps.
"""
from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any, AsyncIterator, Awaitable, Callable, List, Mapping, Optional, Sequence, Type

from ._client import (
    _CORE_FAILURES,
    DEFAULT_BASE_URL,
    DeprecationNotice,
    Page,
    WaitPoll,
    _Deprecations,
    _Fetched,
    build_submit,
    core_options,
    job_page,
    one_job,
    retry_delay,
    split_run_options,
)
from ._errors import ResponseValidationError, to_public
from ._generated.client import AsyncGeneratedClient


class AsyncRendobar:
    """The Rendobar API client for asyncio.

    >>> async with AsyncRendobar() as rb:  # reads RENDOBAR_API_KEY
    ...     job = await rb.jobs.run(type="ffprobe", params={"command": "https://example.com/a.mp4"})

    Use it as an async context manager, or call `aclose()`, to release its connections.
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
        self._core = AsyncGeneratedClient(**core_options(api_key, base_url=base_url, timeout=timeout, app=app))
        self._max_retries = max_retries
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = AsyncJobs(self)
        self.account = AsyncAccount(self)

    async def aclose(self) -> None:
        """Close the underlying HTTP connections. The client cannot be used after."""
        await self._core._client_wrapper.httpx_client.httpx_client.aclose()

    async def __aenter__(self) -> "AsyncRendobar":
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        await self.aclose()

    def _note(self, response: Any, method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    async def _call(self, method: str, path: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        """One API call, with the same retries and errors as `Rendobar._call`."""
        attempt = 0
        while True:
            try:
                response = await fn()
            except _CORE_FAILURES as err:
                delay = retry_delay(err, attempt, self._max_retries)
                if delay is None:
                    raise to_public(err) from err
                attempt += 1
                await asyncio.sleep(delay)
                continue
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

    async def schema(self, type: str) -> Any:
        """One job type's params: `fields`, `inputs` and the full `json_schema`. Public: needs no API key."""
        return (await self._client._call("GET", f"/jobs/types/{type}/schema", lambda: self._raw.get_job_type_schema(type))).data

    async def _job(self, method: str, path: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return (await self._client._call(method, path, fn)).data
        except ResponseValidationError as err:
            return one_job(err)

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
        return await self._job("POST", "/jobs", lambda: self._raw.submit_job(request=request))

    async def get(self, job_id: str) -> Any:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        return await self._job("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(job_id))

    async def list(self, *, status: Optional[str] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page."""
        try:
            res = await self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        except ResponseValidationError as err:
            return job_page(err)
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
        return await self._job("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(job_id))

    async def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        async def fetch() -> _Fetched:
            async with self._raw.download_job_output(job_id) as response:
                return _Fetched(response.headers, b"".join([chunk async for chunk in response.data]))

        return await self._client._call("GET", f"/jobs/{job_id}/download", fetch)

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
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval,
                        throw_on_failure=throw_on_failure, clock=time.monotonic)
        while True:
            job = await self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            pause = poll.step(job)
            if pause is None:
                return job
            await asyncio.sleep(pause)

    async def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *, throw_on_failure: bool = True, **options: Any) -> Any:
        """Submit a job and wait for it. Raises `JobFailedError` if it fails, unless `throw_on_failure=False`."""
        create, wait = split_run_options(options)
        created = await self.create(type, params, inputs, **create)
        return await self.wait(created.id, throw_on_failure=throw_on_failure, **wait)


class AsyncAccount:
    """What this API key's workspace may do."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client

    async def capabilities(self) -> Any:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return (await self._client._call("GET", "/account/capabilities", raw.get_account_capabilities)).data

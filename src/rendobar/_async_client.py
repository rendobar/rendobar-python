"""The asyncio Rendobar client: the same methods as `Rendobar`, awaited.

Everything that is not I/O is shared with the sync client (`_client`): the core
options, the retry decision, body building, the unknown-status fallback,
deprecation notices and the wait poll. This file only awaits and sleeps.
"""
from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any, AsyncIterator, Awaitable, Callable, List, Literal, Mapping, Optional, Sequence, Type, TypeVar, Union, overload

from ._client import (
    _CORE_FAILURES,
    DEFAULT_BASE_URL,
    DeprecationNotice,
    Envelope,
    FinishedJob,
    Page,
    ProgressCallback,
    Response,
    SomeJob,
    UnknownJob,
    WaitPoll,
    _Deprecations,
    _Fetched,
    build_submit,
    core_options,
    job_page,
    one_job,
    JobStatus,
    page_window,
    path_segment,
    require_key,
    resolve_api_key,
    retry_delay,
)
from ._errors import ResponseValidationError, to_public
from ._generated.client import AsyncGeneratedClient
from ._models import AccountCapabilities, JobCancellation, JobComplete, JobCreated, JobReplayed, JobType, JobTypeSchema

T = TypeVar("T")


class AsyncRendobar:
    """The Rendobar API client for asyncio. Takes the same arguments as `Rendobar`.

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
        self._api_key = resolve_api_key(api_key)
        self._core = AsyncGeneratedClient(**core_options(self._api_key, base_url=base_url, timeout=timeout, app=app))
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

    def _note(self, response: Response[object], method: str, path: str) -> None:
        self._deprecations.note(response, method, path)

    async def _call(self, method: str, path: str, fn: Callable[[], Awaitable[Response[T]]], *, public: bool = False) -> T:
        """One API call, with the same retries and errors as `Rendobar._call`."""
        if not public:
            require_key(self._api_key)
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
    """Submit jobs, follow them to the end, and read their output. Same methods and arguments as `Rendobar.jobs`."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.jobs.with_raw_response

    async def types(self) -> List[JobType]:
        """Every live job type. Public: needs no API key."""
        return list((await self._client._call("GET", "/jobs/types", self._raw.list_job_types, public=True)).data)

    async def schema(self, type: str) -> JobTypeSchema:
        """One job type's params: `fields`, `inputs` and the full `json_schema`. Public: needs no API key."""
        return (await self._client._call("GET", f"/jobs/types/{type}/schema", lambda: self._raw.get_job_type_schema(path_segment("type", type)), public=True)).data

    async def _job(self, method: str, path: str, fn: Callable[[], Awaitable[Response[Envelope[T]]]]) -> Union[T, UnknownJob]:
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
        return await self._job("POST", "/jobs", lambda: self._raw.submit_job(request=request))

    async def get(self, job_id: str) -> SomeJob:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        return await self._job("GET", f"/jobs/{job_id}", lambda: self._raw.get_job(path_segment("job_id", job_id)))

    async def list(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Page:
        """One page of jobs, newest first. A job with a status newer than this SDK is an `UnknownJob` in the page.

        `limit` is the page size (1 or more, the API sets the maximum) and `offset` the jobs to skip.
        """
        page_window(limit, offset)
        try:
            res = await self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(status=status, type=type, limit=limit, offset=offset))
        except ResponseValidationError as err:
            return job_page(err)
        jobs: List[SomeJob] = list(res.data)
        return Page(jobs, res.meta)

    async def list_all(self, *, status: Optional[JobStatus] = None, type: Optional[str] = None, page_size: int = 100) -> AsyncIterator[SomeJob]:
        """Every matching job, fetching pages as you iterate."""
        offset = 0
        while True:
            page = await self.list(status=status, type=type, limit=page_size, offset=offset)
            for job in page.data:
                yield job
            offset += len(page.data)
            if not page.data or offset >= page.meta.total:
                return

    async def cancel(self, job_id: str) -> Union[JobCancellation, UnknownJob]:
        """Cancel a job that has not finished."""
        return await self._job("POST", f"/jobs/{job_id}/cancel", lambda: self._raw.cancel_job(path_segment("job_id", job_id)))

    async def download(self, job_id: str) -> bytes:
        """The output file of a completed job, as bytes."""
        async def fetch() -> _Fetched:
            async with self._raw.download_job_output(path_segment("job_id", job_id)) as response:
                return _Fetched(response.headers, b"".join([chunk async for chunk in response.data]))

        return await self._client._call("GET", f"/jobs/{job_id}/download", fetch)

    @overload
    async def wait(self, job_id: str, *, timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                   on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True]) -> JobComplete: ...

    @overload
    async def wait(self, job_id: str, *, timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                   on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool = False) -> FinishedJob: ...

    async def wait(
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
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval,
                        throw_on_failure=throw_on_failure, clock=time.monotonic)
        while True:
            job = await self.get(job_id)
            if on_progress is not None:
                on_progress(job)
            done = poll.finished(job)
            if done is not None:
                return done
            await asyncio.sleep(poll.pause(job))

    @overload
    async def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *,
                  idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[Sequence[str]] = None,
                  callback: Optional[Mapping[str, Any]] = None, force_async: Optional[bool] = None,
                  timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                  on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True] = True) -> JobComplete: ...

    @overload
    async def run(self, type: str, params: Optional[Mapping[str, Any]] = None, inputs: Optional[Mapping[str, Any]] = None, *,
                  idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[Sequence[str]] = None,
                  callback: Optional[Mapping[str, Any]] = None, force_async: Optional[bool] = None,
                  timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                  on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool) -> FinishedJob: ...

    async def run(
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
        created = await self.create(type, params, inputs, idempotency_key=idempotency_key, label=label,
                                    destinations=destinations, callback=callback, force_async=force_async)
        return await self.wait(created.id, timeout=timeout, interval=interval, max_interval=max_interval,
                               on_progress=on_progress, throw_on_failure=throw_on_failure)


class AsyncAccount:
    """What this API key's workspace may do."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client

    async def capabilities(self) -> AccountCapabilities:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        return (await self._client._call("GET", "/account/capabilities", raw.get_account_capabilities)).data

"""The asyncio Rendobar client: the same methods as `Rendobar`, awaited.

Everything that is not I/O is shared with the sync client (`_client`): the core
options, the retry decision, argument checks, body building, the unknown-status
fallback, deprecation notices and the wait poll. This file only awaits and sleeps.
"""
# pyright: strict, reportPrivateUsage=false
from __future__ import annotations

import asyncio
import time

import httpx
from types import TracebackType
from typing import AsyncIterator, Awaitable, Callable, List, Literal, Optional, Type, TypeVar, Union, overload

from ._client import (
    _CORE_FAILURES,
    DEFAULT_BASE_URL,
    DeprecationNotice,
    DownloadTarget,
    ProgressCallback,
    Sink,
    WaitPoll,
    _Deprecations,
    body_failed,
    core_options,
    generate_idempotency_key,
    is_read,
    job_filters,
    job_page,
    list_filters,
    mark_cut_off,
    one_job,
    require_key,
    resolve_api_key,
    retry_delay,
    _EMPTY_REQUEST,
    submit_body,
    status_filter,
    submit_options,
    submitted,
    wait_options,
)
from ._async_resources import (
    AsyncApiKeys,
    AsyncAssets,
    AsyncBilling,
    AsyncCompose,
    AsyncNotifications,
    AsyncOrgs,
    AsyncStorage,
    AsyncUploads,
    AsyncWebhooks,
)
from ._errors import RendobarError, ResponseValidationError, client_closed, to_public
from ._generated.client import AsyncGeneratedClient
from ._plumbing import Envelope, Fetched, Page, Reader, Response, Sent, listed, one, page_window, path_segment
from ._resource_models import DeliveriesRetried, JobLogEntry, JobSort, JobStats, JobTimings, SortOrder, StatsWindow
from ._models import (
    AccountCapabilities,
    Callback,
    FinishedJob,
    JobCancellation,
    JobComplete,
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

T = TypeVar("T")


class AsyncRendobar:
    """The Rendobar API client for asyncio. Takes the same arguments as `Rendobar`.

    >>> async with AsyncRendobar() as rb:  # reads RENDOBAR_API_KEY
    ...     job = await rb.jobs.run({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}})

    Use it as an async context manager, or call `aclose()`, to release its connections.
    A call after `aclose()` raises RendobarError with code `CLIENT_CLOSED`.
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
        self._http = httpx.AsyncClient(timeout=timeout, follow_redirects=True)  # owned here, so aclose() needs no core internals
        self._core = AsyncGeneratedClient(**options, httpx_client=self._http)
        self._max_retries = max_retries
        self._closed = False
        self._deprecations = _Deprecations(on_deprecation)
        self.jobs = AsyncJobs(self)
        self.account = AsyncAccount(self)
        self.billing = AsyncBilling(self)
        self.uploads = AsyncUploads(self)
        self.assets = AsyncAssets(self)
        self.webhooks = AsyncWebhooks(self)
        self.storage = AsyncStorage(self)
        self.api_keys = AsyncApiKeys(self)
        self.orgs = AsyncOrgs(self)
        self.compose = AsyncCompose(self)
        self.notifications = AsyncNotifications(self)

    async def aclose(self) -> None:
        """Close the underlying HTTP connections. Every call after raises RendobarError (code `CLIENT_CLOSED`)."""
        self._closed = True
        await self._http.aclose()

    async def __aenter__(self) -> AsyncRendobar:
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        await self.aclose()

    async def _call(self, method: str, path: str, fn: Callable[[], Awaitable[Response[T]]], *, public: bool = False,
                    deadline: Optional[float] = None, replayable: Optional[bool] = None) -> T:
        """One API call, with the same retries and errors as `Rendobar._call`."""
        if self._closed:
            raise client_closed()
        if not public:
            require_key(self._api_key)
        safe = replayable if replayable is not None else is_read(method)
        attempt = 0
        while True:
            try:
                response = await fn()
            except _CORE_FAILURES as err:
                delay = retry_delay(err, attempt, self._max_retries, deadline=deadline, replayable=safe)
                if delay is None:
                    raise to_public(err) from err
                attempt += 1
                await asyncio.sleep(delay)
                continue
            self._deprecations.note(response, method, path)
            return response.data

    async def _read(self, method: str, path: str, call: Callable[[], Awaitable[Sent]], read: Reader[T], *,
                    replayable: Optional[bool] = None) -> T:
        """`_call` for a generated core call whose answer `read` parses into the public model."""
        async def fetch() -> Fetched[T]:
            sent = await call()
            return Fetched(sent.headers, read(sent.response))

        return await self._call(method, path, fetch, replayable=replayable)


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
        name = path_segment("type", type)
        schema: JobTypeSchema = (await self._client._call("GET", f"/jobs/types/{name}/schema", lambda: self._raw.get_job_type_schema(name), public=True)).data
        return schema

    async def _job(self, method: str, path: str, fn: Callable[[], Awaitable[Response[Envelope[T]]]], deadline: Optional[float] = None) -> Union[T, UnknownJob]:
        try:
            return (await self._client._call(method, path, fn, deadline=deadline, replayable=True)).data
        except ResponseValidationError as err:
            return one_job(err)

    async def create(
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
        async def submit() -> Fetched[Submitted]:
            sent = await self._raw.submit_job(request=_EMPTY_REQUEST, request_options=submit_options(request))
            return Fetched(sent.headers, submitted(sent.response))

        try:
            return await self._client._call("POST", "/jobs", submit, replayable=True)  # keyed: a repeat replays the first job
        except RendobarError as err:
            mark_cut_off(err, key)
            raise

    async def get(self, job_id: str) -> SomeJob:
        """The job now. A status newer than this SDK comes back as `UnknownJob`."""
        return await self._get(job_id, None)

    async def _get(self, job_id: str, deadline: Optional[float]) -> SomeJob:
        safe = path_segment("job_id", job_id)
        return await self._job("GET", f"/jobs/{safe}", lambda: self._raw.get_job(safe), deadline)

    async def list(
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
        """One page of jobs, newest first. Same filters as `Rendobar.jobs.list`."""
        page_window(limit, offset)
        list_filters(status, type)
        job_filters(client, from_, to)
        try:
            res = await self._client._call("GET", "/jobs", lambda: self._raw.list_jobs(
                type=type, limit=limit, offset=offset, sort=sort, order=order, client=client, from_=from_, to=to,
                request_options=status_filter(status)))
        except ResponseValidationError as err:
            return job_page(err)
        jobs: List[SomeJob] = list(res.data)
        return Page(jobs, res.meta)

    async def list_all(
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
    ) -> AsyncIterator[SomeJob]:
        """Every matching job, fetching pages of `page_size` as you iterate. Takes the filters of `list()`."""
        page_window(page_size, None)
        offset = 0
        while True:
            page = await self.list(status=status, type=type, sort=sort, order=order, client=client, from_=from_, to=to,
                                   limit=page_size, offset=offset)
            for job in page.data:
                yield job
            offset += len(page.data)
            if not page.data or offset >= page.meta.total:
                return

    async def cancel(self, job_id: str) -> Union[JobCancellation, UnknownJob]:
        """Cancel a job that has not finished."""
        safe = path_segment("job_id", job_id)
        return await self._job("POST", f"/jobs/{safe}/cancel", lambda: self._raw.cancel_job(safe))

    async def retry_deliveries(self, job_id: str) -> DeliveriesRetried:
        """Put a completed job's failed storage deliveries back on the queue. `retried` says how many."""
        safe = path_segment("job_id", job_id)
        return await self._client._read("POST", f"/jobs/{safe}/deliveries/retry", lambda: self._raw.retry_deliveries(safe),
                                        one(DeliveriesRetried))

    async def logs(self, job_id: str) -> List[JobLogEntry]:
        """The job's log lines, oldest first."""
        safe = path_segment("job_id", job_id)
        return await self._client._read("GET", f"/jobs/{safe}/logs", lambda: self._raw.get_job_logs(safe), listed(JobLogEntry))

    async def get_timings(self, job_id: str) -> JobTimings:
        """Where the job's time went, in milliseconds."""
        safe = path_segment("job_id", job_id)
        return await self._client._read("GET", f"/jobs/{safe}/timings", lambda: self._raw.get_job_timings(safe), one(JobTimings))

    async def stats(self, *, window: Optional[StatsWindow] = None) -> JobStats:
        """Totals, success rate, average duration and spend over `window` (default `"24h"`)."""
        return await self._client._read("GET", "/jobs/stats", lambda: self._raw.get_job_stats(window=window), one(JobStats))

    async def download(self, job_id: str, to: DownloadTarget) -> int:
        """Stream a completed job's output file to `to` and return the bytes written. Same rules as `Rendobar.jobs.download`."""
        safe = path_segment("job_id", job_id)

        async def fetch() -> Fetched[int]:
            # File I/O runs in a worker thread so a slow disk never blocks the event loop.
            async with self._raw.download_job_output(safe) as response:
                sink = await asyncio.to_thread(Sink, to)
                try:
                    async for chunk in response.data:
                        await asyncio.to_thread(sink.write, chunk)
                except BaseException as err:
                    await asyncio.to_thread(sink.fail)
                    raise body_failed(err) from err
                return Fetched(response.headers, await asyncio.to_thread(sink.finish))

        return await self._client._call("GET", f"/jobs/{safe}/download", fetch)

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
                delivery, counted from the poll that saw it. A status newer
                than this SDK ends the wait, returned as an UnknownJob, when the
                job reports it is `terminal`, and is polled until this bound when it is not.
            interval: Seconds before the second poll. Each later pause is 1.5 times longer.
            max_interval: The longest pause between polls, in seconds.
            on_progress: Called with the job after every poll.
            throw_on_failure: Raise `JobFailedError` when the job fails or is
                cancelled. Default: return that job instead.
        """
        wait_options(timeout, interval, max_interval)
        poll = WaitPoll(job_id, timeout=timeout, interval=interval, max_interval=max_interval,
                        throw_on_failure=throw_on_failure, clock=time.monotonic)
        while True:
            job = await self._get(job_id, poll.clock.deadline)
            if on_progress is not None:
                on_progress(job)
            done = poll.finished(job)
            if done is not None:
                return done
            await asyncio.sleep(poll.pause(job))

    @overload
    async def run(self, job: Union[SubmitJob, UntypedJob], *,
                  idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[List[str]] = None,
                  callback: Optional[Callback] = None, force_async: Optional[bool] = None,
                  timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                  on_progress: Optional[ProgressCallback] = None, throw_on_failure: Literal[True] = True) -> JobComplete: ...

    @overload
    async def run(self, job: Union[SubmitJob, UntypedJob], *,
                  idempotency_key: Optional[str] = None, label: Optional[str] = None, destinations: Optional[List[str]] = None,
                  callback: Optional[Callback] = None, force_async: Optional[bool] = None,
                  timeout: Optional[float] = None, interval: float = 2.0, max_interval: float = 10.0,
                  on_progress: Optional[ProgressCallback] = None, throw_on_failure: bool) -> FinishedJob: ...

    async def run(
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
        created = await self.create(job, idempotency_key=idempotency_key, label=label, destinations=destinations,
                                    callback=callback, force_async=force_async)
        return await self.wait(created.id, timeout=timeout, interval=interval, max_interval=max_interval,
                               on_progress=on_progress, throw_on_failure=throw_on_failure)


class AsyncAccount:
    """What this API key's workspace may do."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client

    async def capabilities(self) -> AccountCapabilities:
        """Plan limits and enabled features. Contains no billing data."""
        raw = self._client._core.account.with_raw_response
        capabilities: AccountCapabilities = (await self._client._call("GET", "/account/capabilities", raw.get_account_capabilities)).data
        return capabilities

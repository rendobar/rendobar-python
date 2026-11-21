"""AsyncRendobar against the conformance mock: the scenarios whose logic is not shared with the sync client."""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request

import httpx
import pytest

from rendobar import APITimeoutError, AsyncRendobar, ConflictError, InternalServerError, JobFailed, JobFailedError, NotFoundError, UnknownJob

MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")


def reset(query: str = "") -> None:
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset{query}", method="POST"), timeout=5)


def test_async_scenarios() -> None:
    async def scenarios() -> None:
        reset()
        rb = AsyncRendobar("rb_conformance", base_url=MOCK)
        assert len(await rb.jobs.types()) > 0                                      # C01
        assert (await rb.jobs.get("job_x")).id == "job_x"                          # C02
        assert len([j async for j in rb.jobs.list_all(page_size=50)]) == 120       # C04
        with pytest.raises(NotFoundError) as info:                                 # C05, C12
            await rb.jobs.get("job_404")
        assert info.value.code == "NOT_FOUND" and (info.value.request_id or "").startswith("req_")
        future = await rb.jobs.get("job_future")                                   # C09
        assert isinstance(future, UnknownJob) and future.status == "paused"
        assert len(await rb.jobs.download("job_x")) == 1024                        # C10
        reset("?lose_submit=1")                                                    # C13
        await rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"})
        assert json.load(urllib.request.urlopen(f"{MOCK}/__created", timeout=5))["data"]["count"] == 1

    asyncio.run(scenarios())


class _Recorder(httpx.AsyncHTTPTransport):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await super().handle_async_request(request)


def recording(client: AsyncRendobar) -> _Recorder:
    recorder = _Recorder()
    client._core._client_wrapper.httpx_client.httpx_client._transport = recorder  # noqa: SLF001 (test-only tap)
    return recorder


def test_async_retries_and_errors() -> None:
    async def scenarios() -> None:
        reset()
        async with AsyncRendobar("rb_conformance", base_url=MOCK) as rb:
            started = time.monotonic()                                             # C06
            assert (await rb.jobs.get("job_flaky")).id == "job_flaky"
            assert 0.9 <= time.monotonic() - started < 3
            recorder = recording(rb)                                               # C07
            with pytest.raises(InternalServerError):
                await rb.jobs.get("job_503")
            assert len(recorder.requests) == 3
            recorder.requests.clear()                                              # C18
            with pytest.raises(ConflictError):
                await rb.jobs.get("job_409")
            assert len(recorder.requests) == 1
        assert rb._core._client_wrapper.httpx_client.httpx_client.is_closed  # noqa: SLF001
        fast = AsyncRendobar("k", base_url=MOCK, timeout=2.0, max_retries=0)       # C08
        started = time.monotonic()
        with pytest.raises(APITimeoutError):
            await fast.jobs.get("job_slow")
        assert 1.8 <= time.monotonic() - started < 4
        await fast.aclose()

    asyncio.run(scenarios())


def test_async_run_and_wait() -> None:
    async def scenarios() -> None:
        reset()
        async with AsyncRendobar("rb_conformance", base_url=MOCK) as rb:
            seen: list = []                                                        # C16
            job = await rb.jobs.run("ffprobe", {"command": "https://x/a.mp4"}, interval=0.05, on_progress=lambda j: seen.append(j.status))
            assert seen == ["running", "complete"]
            assert job.status == "complete" and job.output.file is not None and job.output.file.url.startswith("https://")
            with pytest.raises(JobFailedError) as info:                            # C17
                await rb.jobs.wait("job_failed", throw_on_failure=True)
            assert isinstance(info.value.job, JobFailed) and info.value.code == info.value.job.error.code and info.value.code

    asyncio.run(scenarios())

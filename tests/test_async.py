"""AsyncRendobar against the conformance mock: the scenarios whose logic is not shared with the sync client."""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request

import pytest

from rendobar import AsyncRendobar, NotFoundError, UnknownJob

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

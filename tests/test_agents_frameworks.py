"""The LangChain and CrewAI adapters, each through its framework's own tool interface.

They need the optional extras, so these run in the CI job that installs them.
"""
from __future__ import annotations

import os
import urllib.request

import pytest

from rendobar import Rendobar

MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")


@pytest.fixture(autouse=True)
def _fresh() -> None:
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset", method="POST"), timeout=5)


def test_langchain_tools_run_through_invoke() -> None:
    pytest.importorskip("langchain_core")
    from rendobar.agents.langchain import rendobar_tools

    tools = {t.name: t for t in rendobar_tools(Rendobar("k", base_url=MOCK))}
    assert sorted(tools) == ["get_job", "list_job_types", "probe_media", "run_job"]
    created = tools["run_job"].invoke({"type": "ffprobe", "params": {"command": "https://x/a.mp4"}, "wait": False})
    assert created["id"].startswith("job_")
    assert tools["get_job"].invoke({"id": "job_404"})["error"]["code"] == "NOT_FOUND"


def test_crewai_tools_run_through_run() -> None:
    pytest.importorskip("crewai")
    from rendobar.agents.crewai import rendobar_tools

    tools = {t.name: t for t in rendobar_tools(Rendobar("k", base_url=MOCK))}
    assert sorted(tools) == ["get_job", "list_job_types", "probe_media", "run_job"]
    created = tools["run_job"].run(type="ffprobe", params={"command": "https://x/a.mp4"}, wait=False)
    assert created["id"].startswith("job_")
    assert tools["get_job"].run(id="job_404")["error"]["code"] == "NOT_FOUND"

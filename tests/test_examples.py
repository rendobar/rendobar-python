"""The framework examples in examples/, run for real against the conformance mock.

Each submits a job, refuses an unsigned webhook, and accepts a signed one.
They need FastAPI and Django, which the CI agents job installs.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import sys
import time
import types
import urllib.request
from pathlib import Path

import pytest

MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")
SECRET = "whsec_examples"
# The shared vectors' body: a real delivery envelope, which carries data.jobId.
EVENT = json.loads((Path(__file__).parent / "fixtures" / "webhook-vectors.json").read_text())["body"].encode()
sys.path.insert(0, str(Path(__file__).parent.parent / "examples"))


def signed() -> dict:
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), ts.encode() + b"." + EVENT, hashlib.sha256).hexdigest()
    return {"X-Rendobar-Timestamp": ts, "X-Rendobar-Signature": f"sha256={sig}", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _fresh() -> None:
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset", method="POST"), timeout=5)


def test_fastapi_example() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from rendobar import AsyncRendobar

    fastapi_app = importlib.import_module("fastapi_app")
    client = TestClient(fastapi_app.create_app(AsyncRendobar("rb_test", base_url=MOCK), SECRET))
    created = client.post("/videos", json={"url": "https://x/a.mp4"})
    assert created.status_code == 202 and created.json()["job_id"].startswith("job_")
    assert client.post("/rendobar-webhook", content=EVENT).status_code == 401
    assert client.post("/rendobar-webhook", content=EVENT, headers=signed()).status_code == 204


def test_fastapi_example_refuses_to_start_without_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from rendobar import AsyncRendobar

    monkeypatch.delenv("RENDOBAR_WEBHOOK_SECRET", raising=False)
    fastapi_app = importlib.import_module("fastapi_app")
    with pytest.raises(KeyError, match="RENDOBAR_WEBHOOK_SECRET"):
        fastapi_app.create_app(AsyncRendobar("rb_test", base_url=MOCK))


def test_django_example(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("django")
    import django
    from django.conf import settings

    monkeypatch.setenv("RENDOBAR_API_KEY", "rb_test")
    monkeypatch.setenv("RENDOBAR_API_URL", MOCK)
    monkeypatch.setenv("RENDOBAR_WEBHOOK_SECRET", SECRET)
    if not settings.configured:
        urls = types.ModuleType("example_urls")
        sys.modules["example_urls"] = urls
        settings.configure(ROOT_URLCONF="example_urls", ALLOWED_HOSTS=["testserver"], SECRET_KEY="test", MIDDLEWARE=[])
        django.setup()
        from django.urls import path

        views = importlib.import_module("django_views")
        setattr(urls, "urlpatterns", [path("videos", views.submit), path("rendobar-webhook", views.webhook)])  # a module built at runtime
    from django.test import Client

    client = Client()
    created = client.post("/videos", data=json.dumps({"url": "https://x/a.mp4"}), content_type="application/json")
    assert created.status_code == 202 and json.loads(created.content)["job_id"].startswith("job_")
    assert client.post("/rendobar-webhook", data=EVENT, content_type="application/json").status_code == 401
    h = signed()
    extra = {"HTTP_X_RENDOBAR_TIMESTAMP": h["X-Rendobar-Timestamp"], "HTTP_X_RENDOBAR_SIGNATURE": h["X-Rendobar-Signature"]}
    assert client.post("/rendobar-webhook", data=EVENT, content_type="application/json", **extra).status_code == 204

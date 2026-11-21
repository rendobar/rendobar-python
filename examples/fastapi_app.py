"""FastAPI: submit a job from a route, and receive Rendobar's webhook.

    pip install rendobar fastapi uvicorn
    RENDOBAR_API_KEY=rb_... RENDOBAR_WEBHOOK_SECRET=... uvicorn examples.fastapi_app:app
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from rendobar import AsyncRendobar
from rendobar import WebhookSignatureError
from rendobar.webhooks import JobCompletedEvent, parse


class VideoIn(BaseModel):
    url: str


def create_app(rb: Optional[AsyncRendobar] = None, webhook_secret: Optional[str] = None) -> FastAPI:
    client = rb if rb is not None else AsyncRendobar()  # reads RENDOBAR_API_KEY
    # Required: a missing secret stops the app at startup (KeyError), never verifies against "".
    secret = webhook_secret if webhook_secret is not None else os.environ["RENDOBAR_WEBHOOK_SECRET"]
    app = FastAPI()

    @app.post("/videos", status_code=202)
    async def submit(video: VideoIn) -> dict:
        # Answers at once. The result arrives on the webhook below.
        job = await client.jobs.create({"type": "ffprobe", "params": {"command": video.url}})
        return {"job_id": job.id}

    @app.post("/rendobar-webhook", status_code=204)
    async def webhook(request: Request) -> None:
        body = await request.body()  # the exact bytes the signature covers
        try:
            event = parse(body, dict(request.headers), secret)
        except WebhookSignatureError:
            raise HTTPException(status_code=401) from None
        if isinstance(event, JobCompletedEvent):
            print("complete", event.data.job_id)

    return app


app = create_app() if os.environ.get("RENDOBAR_API_KEY") else None

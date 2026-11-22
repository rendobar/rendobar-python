"""Django: the same two views. Route them in your urls.py:

    path("videos", views.submit), path("rendobar-webhook", views.webhook)

    pip install rendobar django
"""
from __future__ import annotations

import json
import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rendobar import Rendobar
from rendobar import WebhookSignatureError
from rendobar.webhooks import JobCompletedWebhookEvent, parse

rb = Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"))  # reads RENDOBAR_API_KEY
# Required: a missing secret stops Django at startup (KeyError), never verifies against "".
WEBHOOK_SECRET = os.environ["RENDOBAR_WEBHOOK_SECRET"]


@csrf_exempt
@require_POST
def submit(request: HttpRequest) -> JsonResponse:
    url = json.loads(request.body)["url"]
    job = rb.jobs.create({"type": "ffprobe", "params": {"command": url}})
    return JsonResponse({"job_id": job.id}, status=202)


@csrf_exempt  # Rendobar signs its webhooks, it cannot send your CSRF token
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = parse(request.body, dict(request.headers), WEBHOOK_SECRET)
    except WebhookSignatureError:
        return HttpResponse(status=401)
    if isinstance(event, JobCompletedWebhookEvent):
        print("complete", event.data.job_id)
    return HttpResponse(status=204)

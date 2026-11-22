"""A webhook receiver on the standard library: verify each delivery, then handle it by its typed event.

    RENDOBAR_WEBHOOK_SECRET=whsec_... PORT=8000 python main.py    # serve
    RENDOBAR_API_KEY=rb_... python main.py --self-test             # manage an endpoint, then test the receiver

Answer 2xx to every genuine delivery, including events you do not handle, so
Rendobar does not retry it. Answer 401 to anything not signed with your secret.

The self-test creates a real webhook endpoint, reads, lists and updates it,
sends it a test event, reads and retries that delivery, rotates its secret and
deletes it (also when a step fails). Rendobar cannot reach a local server, so
the receiver is then proven with deliveries signed by that endpoint's real
secret, the way Rendobar signs them.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, NoReturn, Optional, Tuple

from rendobar import Rendobar, RendobarError, WebhookSignatureError
from rendobar.webhooks import (
    JobCompletedWebhookEvent,
    JobFailedWebhookEvent,
    TestWebhookEvent,
    UnknownWebhookEvent,
    WebhookEvent,
    parse,
)


def handle(event: WebhookEvent) -> str:
    """Your app's work for each event. Returns a line for the log."""
    if isinstance(event, JobCompletedWebhookEvent):
        return f"job.completed {event.data.job_id}: {[file.url for file in event.data.output.files]}"
    if isinstance(event, JobFailedWebhookEvent):
        return f"job.failed {event.data.job_id}: {event.data.error.code}"
    if isinstance(event, TestWebhookEvent):
        return f"test from endpoint {event.data.endpoint_id}"
    if isinstance(event, UnknownWebhookEvent):
        # An event or envelope version newer than this SDK: acknowledge it, handle it after upgrading.
        return f"unknown {event.event} ({event.reason})"
    return f"{event.event}: not handled"  # the other known events


def make_server(secret: str, host: str, port: int, record: Callable[[str], None]) -> ThreadingHTTPServer:
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                event = parse(body, dict(self.headers.items()), secret)  # the raw bytes, exactly as received
            except WebhookSignatureError:
                return self.answer(401)
            except RendobarError:  # signed, but not a JSON object
                return self.answer(400)
            record(handle(event))
            self.answer(204)

        def answer(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return ThreadingHTTPServer((host, port), Receiver)


# ── self-test: sign deliveries the way Rendobar does and post them to the receiver ──

def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def sign(body: bytes, secret: str, timestamp: int) -> Dict[str, str]:
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Rendobar-Timestamp": str(timestamp), "X-Rendobar-Signature": f"sha256={digest}"}


def envelope(event: str, data: Dict[str, object]) -> bytes:
    return json.dumps({"version": "1", "event": event, "deliveryId": "dlv_example", "timestamp": int(time.time() * 1000),
                       "orgId": "org_example", "data": data}).encode()


def post(url: str, body: bytes, headers: Dict[str, str]) -> int:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status: int = response.status
            return status
    except urllib.error.HTTPError as err:
        return err.code


MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"


def manage_endpoint(rb: Rendobar) -> str:
    """Create, read, list, update, test and rotate an endpoint, then delete it. Returns its last signing secret."""
    name = f"example-{secrets.token_hex(4)}"
    endpoint = rb.webhooks.create(name=name, url="https://example.com/rendobar-webhooks",
                                  subscribed_events=["job.completed", "job.failed"])
    secret = endpoint.signing_secret  # plaintext only here and on rotate: store it
    print(f"created endpoint {endpoint.id}")
    if not secret:
        fail("create returned no signing secret")
    try:
        if rb.webhooks.get(endpoint.id).id != endpoint.id:
            fail("get returned another endpoint")
        listed = rb.webhooks.list()
        if not any(each.id == endpoint.id for each in listed) or listed.meta.total < 1:
            fail(f"the new endpoint is not listed: {listed!r}")
        updated = rb.webhooks.update(endpoint.id, name=f"{name}-renamed")
        if MOCK:
            print("SKIP (mock: update does not echo the new name)")
        elif updated.name != f"{name}-renamed":
            fail(f"update left the name {updated.name!r}")

        # A test event. Rendobar records the delivery whether or not the URL answered.
        test = rb.webhooks.test(endpoint.id)
        print(f"test delivery: delivered {test.delivered}, status {test.status_code}, {test.response_time_ms} ms")
        deliveries = rb.webhooks.list_deliveries(endpoint_id=endpoint.id, limit=5)
        if not deliveries.data:
            fail("the test delivery was not recorded")
        delivery = deliveries.data[0]
        if not MOCK and delivery.endpoint_id != endpoint.id:
            fail(f"delivery {delivery.id} belongs to {delivery.endpoint_id}")
        retried = rb.webhooks.retry_delivery(delivery.id)
        print(f"retried delivery {retried.id}: {retried.status}")
        if retried.id != delivery.id:
            fail(f"retry answered for {retried.id}")

        # Rotate. For 24 hours deliveries carry both signatures, so a receiver can switch.
        rotated = rb.webhooks.rotate_secret(endpoint.id)
        if MOCK:
            print("SKIP (mock: rotate returns the same secret)")
        elif rotated.signing_secret == secret:
            fail("rotate kept the old secret")
        return rotated.signing_secret
    finally:
        rb.webhooks.delete(endpoint.id)
        if not MOCK and any(each.id == endpoint.id for each in rb.webhooks.list()):
            fail("the endpoint is still listed after delete")
        print(f"deleted endpoint {endpoint.id}")


def self_test() -> None:
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-webhook-receiver") as rb:
        secret = manage_endpoint(rb)
    timing = {"createdAt": 1731000000000, "dispatchedAt": 1731000000100, "startedAt": 1731000000200}
    completed = envelope("job.completed", {
        "jobId": "job_example", "jobType": "ffmpeg", "status": "complete",
        "output": {"files": [{"url": "https://cdn.rendobar.com/example.mp4", "path": "clip.mp4", "type": "video", "size": 1024}]},
        "timing": dict(timing, completedAt=1731000001000),
    })
    failed = envelope("job.failed", {
        "jobId": "job_example", "jobType": "ffmpeg", "status": "failed",
        "error": {"code": "FFMPEG_ERROR", "message": "Invalid data found when processing input", "retryable": False},
        "timing": dict(timing, failedAt=1731000001000),
    })
    newer = envelope("job.paused", {"jobId": "job_example"})
    now = int(time.time())
    cases: List[Tuple[str, bytes, Dict[str, str], int, Optional[str]]] = [
        ("job.completed", completed, sign(completed, secret, now), 204, "job.completed job_example: ['https://cdn.rendobar.com/example.mp4']"),
        ("job.failed", failed, sign(failed, secret, now), 204, "job.failed job_example: FFMPEG_ERROR"),
        ("an event newer than the SDK", newer, sign(newer, secret, now), 204, "unknown job.paused (unknown_event)"),
        ("unsigned", completed, {"Content-Type": "application/json"}, 401, None),
        ("signed with another secret", completed, sign(completed, f"whsec_{secrets.token_hex(32)}", now), 401, None),
        ("301 seconds old", completed, sign(completed, secret, now - 301), 401, None),
        ("body changed after signing", completed + b" ", sign(completed, secret, now), 401, None),
    ]

    log: List[str] = []
    server = make_server(secret, "127.0.0.1", 0, log.append)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/rendobar-webhook"
    try:
        for name, body, headers, want, line in cases:
            before = len(log)
            got = post(url, body, headers)
            print(f"{name}: {got}")
            if got != want:
                fail(f"{name}: answered {got}, expected {want}")
            handled = log[before:]
            if handled != ([line] if line is not None else []):
                fail(f"{name}: handled {handled}, expected {line}")
    finally:
        server.shutdown()
        server.server_close()


def serve() -> None:
    secret = os.environ["RENDOBAR_WEBHOOK_SECRET"]  # no default: a receiver without its secret must not start
    server = make_server(secret, os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000")),
                         lambda line: print(line, flush=True))
    print(f"listening on port {server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    else:
        serve()

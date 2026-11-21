"""rendobar.webhooks.verify agrees with every shared test vector (rendobar/openapi conformance/webhook-vectors.json)."""
import json
from pathlib import Path

import pytest

from rendobar.webhooks import verify

VECTORS = json.loads((Path(__file__).parent / "fixtures" / "webhook-vectors.json").read_text())


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_vector(case: dict) -> None:
    got = verify(
        case.get("body", VECTORS["body"]),
        case["headers"],
        case.get("secret", VECTORS["secret"]),
        now=case.get("now", VECTORS["timestamp"]),
    )
    assert got is case["expect"]


def test_bytes_body_is_accepted() -> None:
    case = VECTORS["cases"][0]
    assert verify(VECTORS["body"].encode(), case["headers"], VECTORS["secret"], now=VECTORS["timestamp"])


@pytest.mark.parametrize("secret", ["", " ", "\t\n"])
def test_a_blank_secret_never_verifies(secret: str) -> None:
    import hashlib
    import hmac

    ts = str(VECTORS["timestamp"])
    sig = hmac.new(secret.encode(), ts.encode() + b"." + VECTORS["body"].encode(), hashlib.sha256).hexdigest()
    headers = {"x-rendobar-signature": f"sha256={sig}", "x-rendobar-timestamp": ts}
    assert verify(VECTORS["body"], headers, secret, now=VECTORS["timestamp"]) is False


def test_a_non_ascii_previous_signature_is_false_not_an_error() -> None:
    headers = {
        "x-rendobar-signature": "sha256=00",
        "x-rendobar-signature-previous": "sha256=éé\udcff",
        "x-rendobar-timestamp": str(VECTORS["timestamp"]),
    }
    assert verify(VECTORS["body"], headers, VECTORS["secret"], now=VECTORS["timestamp"]) is False


def test_a_bare_hex_signature_is_refused() -> None:
    signature = VECTORS["cases"][0]["headers"]["x-rendobar-signature"]
    headers = {"x-rendobar-signature": signature.removeprefix("sha256="), "x-rendobar-timestamp": str(VECTORS["timestamp"])}
    assert verify(VECTORS["body"], headers, VECTORS["secret"], now=VECTORS["timestamp"]) is False


def test_the_tolerance_is_300_seconds_inclusive() -> None:
    case = VECTORS["cases"][0]
    assert verify(VECTORS["body"], case["headers"], VECTORS["secret"], now=VECTORS["timestamp"] + 300) is True
    assert verify(VECTORS["body"], case["headers"], VECTORS["secret"], now=VECTORS["timestamp"] + 301) is False


# ── parse(): typed events ─────────────────────────────────────────────

import hashlib  # noqa: E402
from typing import Dict, Tuple  # noqa: E402
import hmac  # noqa: E402

from rendobar import JobError, RendobarError, WebhookSignatureError  # noqa: E402
from rendobar import webhooks  # noqa: E402
from rendobar.webhooks import (  # noqa: E402
    BalanceLowEvent,
    JobCompletedEvent,
    JobFailedEvent,
    UnknownWebhookEvent,
    parse,
)

SECRET = "whsec_parse"
NOW = 1_700_000_000


def signed(body: Dict[str, object]) -> Tuple[str, Dict[str, str]]:
    raw = json.dumps(body)
    sig = hmac.new(SECRET.encode(), f"{NOW}.{raw}".encode(), hashlib.sha256).hexdigest()
    return raw, {"X-Rendobar-Signature": f"sha256={sig}", "X-Rendobar-Timestamp": str(NOW)}


def envelope(event: str, data: dict, version: str = "1") -> dict:
    return {"version": version, "event": event, "deliveryId": "dlv_1", "timestamp": NOW * 1000, "orgId": "org_1", "data": data}


COMPLETED = {
    "jobId": "job_1", "jobType": "ffprobe", "status": "complete",
    "output": {"data": {"format": {}}, "file": None, "files": []},
    "cost": {"amount": 2_100_000, "currency": "USD", "formatted": "$0.0021", "breakdown": "1 s"},
    "timing": {"createdAt": 1, "completedAt": 2}, "brandNewField": True,
}


def test_parse_types_a_known_event() -> None:
    event = parse(*signed(envelope("job.completed", COMPLETED)), SECRET, now=NOW)
    assert isinstance(event, JobCompletedEvent)
    assert event.data.job_id == "job_1" and event.data.cost is not None and event.data.cost.amount == 2_100_000
    assert event.delivery_id == "dlv_1" and event.timestamp == NOW * 1000 and event.data.timing.completed_at == 2


def test_parse_types_failed_balance_and_test_events() -> None:
    failed = {"jobId": "job_2", "jobType": "ffmpeg", "status": "failed", "timing": {"createdAt": 1, "failedAt": 3},
              "error": {"code": "PROCESSING_FAILED", "message": "exit 1", "retryable": False}}
    event = parse(*signed(envelope("job.failed", failed)), SECRET, now=NOW)
    assert isinstance(event, JobFailedEvent) and isinstance(event.data.error, JobError)
    low = {"balance": 1_000_000_000, "balanceFormatted": "$1.00", "threshold": 2_000_000_000, "thresholdFormatted": "$2.00",
           "triggeredByJobId": "job_3", "triggeredByJobType": "ffmpeg"}
    assert isinstance(parse(*signed(envelope("balance.low", low)), SECRET, now=NOW), BalanceLowEvent)
    ping = parse(*signed(envelope("test", {"message": "hi", "endpointId": "whe_1"})), SECRET, now=NOW)
    assert isinstance(ping, webhooks.TestEvent) and ping.data.endpoint_id == "whe_1"


@pytest.mark.parametrize("body", [
    envelope("job.teleported", {"jobId": "job_1"}),           # a new event
    envelope("job.completed", COMPLETED, version="2"),       # a new envelope version
    envelope("job.completed", {"jobId": "job_1"}),           # a known event whose payload changed
])
def test_what_the_sdk_cannot_type_is_an_unknown_event_never_an_error(body: dict) -> None:
    event = parse(*signed(body), SECRET, now=NOW)
    assert isinstance(event, UnknownWebhookEvent) and event.raw == body and event.event == body["event"]


def test_a_bad_signature_raises() -> None:
    raw, headers = signed(envelope("test", {"message": "hi", "endpointId": "whe_1"}))
    with pytest.raises(WebhookSignatureError) as info:
        parse(raw, headers, "whsec_other", now=NOW)
    assert isinstance(info.value, RendobarError) and info.value.code == "INVALID_SIGNATURE"
    with pytest.raises(WebhookSignatureError):
        parse(raw, headers, "   ", now=NOW)


def test_a_signed_body_that_is_not_json_raises_a_rendobar_error() -> None:
    raw = "not json"
    sig = hmac.new(SECRET.encode(), f"{NOW}.{raw}".encode(), hashlib.sha256).hexdigest()
    with pytest.raises(RendobarError):
        parse(raw, {"x-rendobar-signature": f"sha256={sig}", "x-rendobar-timestamp": str(NOW)}, SECRET, now=NOW)

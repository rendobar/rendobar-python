"""Verify and read Rendobar webhook and callback deliveries.

    from rendobar.webhooks import JobCompletedEvent, parse

    event = parse(request.body, request.headers, os.environ["RENDOBAR_WEBHOOK_SECRET"])
    if isinstance(event, JobCompletedEvent):
        print(event.data.job_id, event.data.output.files[0].url)

`parse()` checks the signature (raising `WebhookSignatureError` when it does not
hold) and returns the event typed by its `event` name. An event or envelope
version this SDK does not know comes back as `UnknownWebhookEvent` with the
body as sent, never an exception, so a new event never breaks your handler.

Rendobar signs each delivery with HMAC-SHA256 over `"{timestamp}.{body}"`,
sent as `X-Rendobar-Signature: sha256=<hex>` with `X-Rendobar-Timestamp`
(unix seconds). During a secret rotation the previous secret's signature also
arrives as `X-Rendobar-Signature-Previous`, so a receiver holding either
secret verifies. Same algorithm and the same shared test vectors as
`@rendobar/sdk/webhooks`. `verify()` is that check alone, as a bool, for code
that reads the body itself.

Pass the RAW body bytes or text exactly as received. Parsing and re-serialising
the JSON first changes the bytes and the signature will not match.

The event models are generated from the spec's `webhooks` section: one
`<Event>WebhookEvent` envelope (`version`, `event`, `delivery_id`, `timestamp`
in Unix milliseconds, `org_id`, `data`) per event, with its `<Event>Data`. A new
event reaches this module with the next regeneration.
"""
# pyright: strict
from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from typing import Dict, Literal, Mapping, Optional, Sequence, Union, cast, get_args, get_type_hints

import pydantic

from ._errors import RendobarError, WebhookSignatureError, as_mapping, is_text
from ._generated.types.balance_depleted_data import BalanceDepletedData
from ._generated.types.balance_low_data import BalanceLowData
from ._generated.types.job_cancelled_data import JobCancelledData
from ._generated.types.job_completed_data import JobCompletedData
from ._generated.types.job_created_data import JobCreatedData
from ._generated.types.job_deliveries_settled_data import JobDeliveriesSettledData
from ._generated.types.job_delivery_failed_data import JobDeliveryFailedData
from ._generated.types.job_delivery_succeeded_data import JobDeliverySucceededData
from ._generated.types.job_failed_data import JobFailedData
from ._generated.types.job_started_data import JobStartedData
from ._generated.types.settled_delivery import SettledDelivery
from ._generated.types.test_event_data import TestEventData
from ._generated.types.webhook_job_cost import WebhookJobCost
from ._generated.types.webhook_job_step import WebhookJobStep
from ._generated.types.webhook_payload import (
    WebhookPayload,
    WebhookPayload_BalanceDepleted,
    WebhookPayload_BalanceLow,
    WebhookPayload_JobCancelled,
    WebhookPayload_JobCompleted,
    WebhookPayload_JobCreated,
    WebhookPayload_JobDeliveriesSettled,
    WebhookPayload_JobDeliveryFailed,
    WebhookPayload_JobDeliverySucceeded,
    WebhookPayload_JobFailed,
    WebhookPayload_JobStarted,
    WebhookPayload_Test,
)
from ._models import publish

__all__ = [
    "parse", "verify", "DEFAULT_TOLERANCE_SECONDS", "WebhookSignatureError",
    "WebhookEvent", "KnownWebhookEvent", "UnknownWebhookEvent", "UnknownReason",
    "JobCreatedWebhookEvent", "JobStartedWebhookEvent", "JobCompletedWebhookEvent", "JobFailedWebhookEvent",
    "JobCancelledWebhookEvent", "JobDeliverySucceededWebhookEvent", "JobDeliveryFailedWebhookEvent",
    "JobDeliveriesSettledWebhookEvent", "BalanceLowWebhookEvent", "BalanceDepletedWebhookEvent", "TestWebhookEvent",
    "JobCreatedData", "JobStartedData", "JobCompletedData", "JobFailedData", "JobCancelledData",
    "JobDeliverySucceededData", "JobDeliveryFailedData", "JobDeliveriesSettledData", "SettledDelivery",
    "BalanceLowData", "BalanceDepletedData", "TestEventData", "WebhookJobCost", "WebhookJobStep",
]

DEFAULT_TOLERANCE_SECONDS = 300

_SIGNATURE = "x-rendobar-signature"
_SIGNATURE_PREVIOUS = "x-rendobar-signature-previous"
_TIMESTAMP = "x-rendobar-timestamp"


# ── signatures ────────────────────────────────────────────────────────

def _header(headers: Mapping[str, object], name: str) -> Optional[str]:
    for key, value in headers.items():
        if key.lower() == name:
            if isinstance(value, (list, tuple)):
                # Some frameworks give each header as a list of its values; isinstance cannot see the item type.
                values = cast(Sequence[object], value)
                value = values[0] if values else None
            return None if value is None else str(value)
    return None


def _matches(signed: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):  # the prefix is part of the format: a bare hex digest is refused
        return False
    expected = signature[7:]
    computed = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    # Compare bytes: compare_digest refuses a str with non-ASCII characters, and a
    # header is attacker-controlled, so a garbage signature must be False, not a crash.
    return hmac.compare_digest(expected.encode("utf-8", "surrogatepass"), computed.encode())  # constant time


def verify(
    body: Union[str, bytes],
    headers: Mapping[str, object],
    secret: str,
    *,
    tolerance_seconds: float = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> bool:
    """True when the delivery is signed with `secret` (or the previous secret) and is fresh.

    An empty or blank `secret` always returns False: anyone can sign with an empty
    key, so accepting one would accept forged deliveries. So does a signature
    without its `sha256=` prefix. Never raises on a malformed header.
    """
    if not is_text(secret) or not secret.strip():
        return False
    signature = _header(headers, _SIGNATURE)
    timestamp = _header(headers, _TIMESTAMP)
    if not signature or not timestamp:
        return False
    try:
        ts = float(timestamp)
    except ValueError:
        return False
    if not math.isfinite(ts):
        return False
    if math.isfinite(tolerance_seconds):
        current = time.time() if now is None else now
        if abs(math.floor(current) - ts) > tolerance_seconds:
            return False
    raw = body.encode() if isinstance(body, str) else body
    signed = timestamp.encode() + b"." + raw
    if _matches(signed, signature, secret):
        return True
    previous = _header(headers, _SIGNATURE_PREVIOUS)
    return previous is not None and _matches(signed, previous, secret)


# ── events ────────────────────────────────────────────────────────────

# The generated core inlines each variant of the spec's WebhookPayload union; these are
# their spec names (the `<Event>WebhookEvent` components). Check with isinstance.
JobCreatedWebhookEvent = WebhookPayload_JobCreated
JobStartedWebhookEvent = WebhookPayload_JobStarted
JobCompletedWebhookEvent = WebhookPayload_JobCompleted
JobFailedWebhookEvent = WebhookPayload_JobFailed
JobCancelledWebhookEvent = WebhookPayload_JobCancelled
JobDeliverySucceededWebhookEvent = WebhookPayload_JobDeliverySucceeded
JobDeliveryFailedWebhookEvent = WebhookPayload_JobDeliveryFailed
JobDeliveriesSettledWebhookEvent = WebhookPayload_JobDeliveriesSettled
BalanceLowWebhookEvent = WebhookPayload_BalanceLow
BalanceDepletedWebhookEvent = WebhookPayload_BalanceDepleted
TestWebhookEvent = WebhookPayload_Test

publish({
    "JobCreatedWebhookEvent": JobCreatedWebhookEvent,
    "JobStartedWebhookEvent": JobStartedWebhookEvent,
    "JobCompletedWebhookEvent": JobCompletedWebhookEvent,
    "JobFailedWebhookEvent": JobFailedWebhookEvent,
    "JobCancelledWebhookEvent": JobCancelledWebhookEvent,
    "JobDeliverySucceededWebhookEvent": JobDeliverySucceededWebhookEvent,
    "JobDeliveryFailedWebhookEvent": JobDeliveryFailedWebhookEvent,
    "JobDeliveriesSettledWebhookEvent": JobDeliveriesSettledWebhookEvent,
    "BalanceLowWebhookEvent": BalanceLowWebhookEvent,
    "BalanceDepletedWebhookEvent": BalanceDepletedWebhookEvent,
    "TestWebhookEvent": TestWebhookEvent,
})

KnownWebhookEvent = Union[
    JobCreatedWebhookEvent, JobStartedWebhookEvent, JobCompletedWebhookEvent, JobFailedWebhookEvent,
    JobCancelledWebhookEvent, JobDeliverySucceededWebhookEvent, JobDeliveryFailedWebhookEvent,
    JobDeliveriesSettledWebhookEvent, BalanceLowWebhookEvent, BalanceDepletedWebhookEvent, TestWebhookEvent,
]


# Why parse() could not type a genuine delivery.
UnknownReason = Literal["unknown_event", "unknown_version", "invalid_payload"]


class UnknownWebhookEvent:
    """A genuine delivery this SDK version cannot type. `raw` holds the body as sent.

    `reason` says why: `unknown_event` (an event newer than this SDK),
    `unknown_version` (a new envelope version) or `invalid_payload` (a known
    event whose payload this SDK cannot read). Handle the events you know and
    let this one through.
    """

    def __init__(self, raw: Mapping[str, object], reason: UnknownReason) -> None:
        self.raw: Dict[str, object] = dict(raw)
        self.reason: UnknownReason = reason
        event, version = raw.get("event"), raw.get("version")
        self.event: str = event if isinstance(event, str) else ""
        self.version: str = version if isinstance(version, str) else ""

    def __repr__(self) -> str:
        return f"UnknownWebhookEvent(event={self.event!r}, version={self.version!r}, reason={self.reason!r})"


# What parse() returns. Check with isinstance; anything this SDK cannot type is an UnknownWebhookEvent.
WebhookEvent = Union[KnownWebhookEvent, UnknownWebhookEvent]

_EVENTS: pydantic.TypeAdapter[KnownWebhookEvent] = pydantic.TypeAdapter(WebhookPayload)
_VERSION = "1"  # the envelope version these models describe
# Every event name the generated union types, read from its variants.
_KNOWN_EVENTS = frozenset(str(get_args(get_type_hints(variant)["event"])[0]) for variant in get_args(KnownWebhookEvent))


def parse(
    body: Union[str, bytes],
    headers: Mapping[str, object],
    secret: str,
    *,
    tolerance_seconds: float = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> WebhookEvent:
    """Verify a delivery and return its event, typed by `event`.

    Raises `WebhookSignatureError` when the signature does not hold (see
    `verify()`). A genuine delivery this SDK cannot type comes back as
    `UnknownWebhookEvent`, never an exception.
    """
    if not verify(body, headers, secret, tolerance_seconds=tolerance_seconds, now=now):
        raise WebhookSignatureError(
            "The delivery is not signed with this secret, or is older than the tolerance. Check RENDOBAR_WEBHOOK_SECRET and that the body is the raw bytes received."
        )
    try:
        decoded: object = json.loads(body)
    except ValueError:
        decoded = None
    envelope = as_mapping(decoded)
    if envelope is None:
        raise RendobarError("The delivery is signed but its body is not a JSON object.", code="INVALID_RESPONSE")
    if envelope.get("version") != _VERSION:
        return UnknownWebhookEvent(envelope, "unknown_version")
    if envelope.get("event") not in _KNOWN_EVENTS:
        return UnknownWebhookEvent(envelope, "unknown_event")
    try:
        return _EVENTS.validate_python(envelope)
    except pydantic.ValidationError:
        return UnknownWebhookEvent(envelope, "invalid_payload")

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

The event models are written from the documented envelope (`version`, `event`,
`deliveryId`, `timestamp` in Unix milliseconds, `orgId`, `data`). They will be
generated from the spec's `webhooks` section once it has one, under the same names.
"""
# pyright: strict
from __future__ import annotations

import hashlib
import hmac
import json
import math
import time
from typing import Dict, List, Literal, Mapping, Optional, Sequence, Union, cast

import pydantic
from pydantic.alias_generators import to_camel

from ._errors import RendobarError, WebhookSignatureError, as_mapping, is_text
from ._models import JobError, JobOutput

__all__ = [
    "parse", "verify", "DEFAULT_TOLERANCE_SECONDS", "WebhookSignatureError",
    "WebhookEvent", "UnknownWebhookEvent",
    "JobCreatedEvent", "JobStartedEvent", "JobCompletedEvent", "JobFailedEvent", "JobCancelledEvent",
    "JobDeliverySucceededEvent", "JobDeliveryFailedEvent", "JobDeliveriesSettledEvent",
    "BalanceLowEvent", "BalanceDepletedEvent", "TestEvent",
    "JobCreatedData", "JobStartedData", "JobCompletedData", "JobFailedData", "JobCancelledData",
    "JobDeliverySucceededData", "JobDeliveryFailedData", "JobDeliveriesSettledData", "SettledDelivery",
    "BalanceLowData", "BalanceDepletedData", "TestEventData", "WebhookCost", "WebhookStep", "Timing",
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

class _Model(pydantic.BaseModel):
    """camelCase on the wire, snake_case in Python; fields the SDK does not know yet are kept, never refused."""

    model_config = pydantic.ConfigDict(frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True)


class Timing(_Model):
    """When the job reached each step, in Unix milliseconds. Each event sets the ones it knows."""

    created_at: int
    dispatched_at: Optional[int] = None
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    failed_at: Optional[int] = None
    cancelled_at: Optional[int] = None


class WebhookStep(_Model):
    id: str
    name: str
    status: str
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class WebhookCost(_Model):
    """What the job was charged. `amount` is in nanodollars (1 USD = 1,000,000,000)."""

    amount: int
    currency: Union[Literal["USD"], str]
    formatted: str
    breakdown: str


class JobCreatedData(_Model):
    job_id: str
    job_type: str
    status: str
    timing: Timing


class JobStartedData(_Model):
    job_id: str
    job_type: str
    status: str
    timing: Timing


class JobCompletedData(_Model):
    """The same `output` GET /jobs/{id} returns for the complete job. `cost` is absent until billing settles."""

    job_id: str
    job_type: str
    status: str
    output: JobOutput
    timing: Timing
    cost: Optional[WebhookCost] = None
    steps: Optional[List[WebhookStep]] = None
    output_category: Optional[str] = None
    media_type: Optional[str] = None


class JobFailedData(_Model):
    job_id: str
    job_type: str
    status: str
    error: JobError
    timing: Timing
    steps: Optional[List[WebhookStep]] = None


class JobCancelledData(_Model):
    job_id: str
    job_type: str
    status: str
    timing: Timing


class JobDeliverySucceededData(_Model):
    """One destination received the output. `url` is absent when `path` is a folder (ends in "/")."""

    job_id: str
    storage_id: str
    status: str
    path: str
    url: Optional[str] = None


class JobDeliveryFailedData(_Model):
    """One destination will not receive the output. `reason` is a delivery reason code."""

    job_id: str
    storage_id: str
    status: str
    reason: str


class SettledDelivery(_Model):
    storage_id: str
    status: Union[Literal["delivered", "failed"], str]
    path: Optional[str] = None
    url: Optional[str] = None
    reason: Optional[str] = None
    renamed: Optional[bool] = None


class JobDeliveriesSettledData(_Model):
    job_id: str
    deliveries: List[SettledDelivery]


class BalanceLowData(_Model):
    """`balance` and `threshold` are in nanodollars."""

    balance: int
    balance_formatted: str
    threshold: int
    threshold_formatted: str
    triggered_by_job_id: str
    triggered_by_job_type: str


class BalanceDepletedData(_Model):
    """`balance` is in nanodollars."""

    balance: int
    balance_formatted: str
    triggered_by_job_id: str
    triggered_by_job_type: str


class TestEventData(_Model):
    message: str
    endpoint_id: str


class _Envelope(_Model):
    version: Literal["1"]
    delivery_id: str
    timestamp: int  # Unix milliseconds
    org_id: str


class JobCreatedEvent(_Envelope):
    event: Literal["job.created"]
    data: JobCreatedData


class JobStartedEvent(_Envelope):
    event: Literal["job.started"]
    data: JobStartedData


class JobCompletedEvent(_Envelope):
    event: Literal["job.completed"]
    data: JobCompletedData


class JobFailedEvent(_Envelope):
    event: Literal["job.failed"]
    data: JobFailedData


class JobCancelledEvent(_Envelope):
    event: Literal["job.cancelled"]
    data: JobCancelledData


class JobDeliverySucceededEvent(_Envelope):
    event: Literal["job.delivery_succeeded"]
    data: JobDeliverySucceededData


class JobDeliveryFailedEvent(_Envelope):
    event: Literal["job.delivery_failed"]
    data: JobDeliveryFailedData


class JobDeliveriesSettledEvent(_Envelope):
    event: Literal["job.deliveries_settled"]
    data: JobDeliveriesSettledData


class BalanceLowEvent(_Envelope):
    event: Literal["balance.low"]
    data: BalanceLowData


class BalanceDepletedEvent(_Envelope):
    event: Literal["balance.depleted"]
    data: BalanceDepletedData


class TestEvent(_Envelope):
    """The ping the dashboard's "Send test" button delivers."""

    event: Literal["test"]
    data: TestEventData


class UnknownWebhookEvent:
    """A genuine delivery this SDK version cannot type: a new event, a new envelope version, or a payload that changed.

    `raw` holds the body as sent. Handle the events you know and let this one through.
    """

    def __init__(self, raw: Mapping[str, object]) -> None:
        self.raw: Dict[str, object] = dict(raw)
        event, version = raw.get("event"), raw.get("version")
        self.event: str = event if isinstance(event, str) else ""
        self.version: str = version if isinstance(version, str) else ""

    def __repr__(self) -> str:
        return f"UnknownWebhookEvent(event={self.event!r}, version={self.version!r})"


_KnownEvent = Union[
    JobCreatedEvent, JobStartedEvent, JobCompletedEvent, JobFailedEvent, JobCancelledEvent,
    JobDeliverySucceededEvent, JobDeliveryFailedEvent, JobDeliveriesSettledEvent,
    BalanceLowEvent, BalanceDepletedEvent, TestEvent,
]
# What parse() returns. Check with isinstance; anything else is an UnknownWebhookEvent.
WebhookEvent = Union[_KnownEvent, UnknownWebhookEvent]

_EVENTS: pydantic.TypeAdapter[_KnownEvent] = pydantic.TypeAdapter(_KnownEvent)


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
    if envelope.get("version") != "1":
        return UnknownWebhookEvent(envelope)
    try:
        return _EVENTS.validate_python(envelope)
    except pydantic.ValidationError:
        return UnknownWebhookEvent(envelope)

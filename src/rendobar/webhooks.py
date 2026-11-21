"""Verify Rendobar webhook and callback signatures.

Rendobar signs each delivery with HMAC-SHA256 over `"{timestamp}.{body}"`,
sent as `X-Rendobar-Signature: sha256=<hex>` with `X-Rendobar-Timestamp`
(unix seconds). During a secret rotation the previous secret's signature also
arrives as `X-Rendobar-Signature-Previous`, so a receiver holding either
secret verifies. Same algorithm and the same shared test vectors as
`@rendobar/sdk/webhooks`.

    from rendobar.webhooks import verify
    if not verify(request.body, request.headers, os.environ["RENDOBAR_WEBHOOK_SECRET"]):
        return 401

Pass the RAW body bytes or text exactly as received. Parsing and re-serialising
the JSON first changes the bytes and the signature will not match.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import time
from typing import Mapping, Optional, Union

DEFAULT_TOLERANCE_SECONDS = 300

_SIGNATURE = "x-rendobar-signature"
_SIGNATURE_PREVIOUS = "x-rendobar-signature-previous"
_TIMESTAMP = "x-rendobar-timestamp"


def _header(headers: Mapping[str, object], name: str) -> Optional[str]:
    for key, value in headers.items():
        if key.lower() == name:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            return None if value is None else str(value)
    return None


def _matches(signed: bytes, signature: str, secret: str) -> bool:
    expected = signature[7:] if signature.startswith("sha256=") else signature
    computed = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, computed)  # constant time


def verify(
    body: Union[str, bytes],
    headers: Mapping[str, object],
    secret: str,
    *,
    tolerance_seconds: float = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> bool:
    """True when the delivery is signed with `secret` (or the previous secret) and is fresh."""
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
    return bool(previous) and _matches(signed, previous, secret)

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

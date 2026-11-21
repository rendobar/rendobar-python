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

"""Deprecation notices are advisory: they never change the outcome of a call."""
from __future__ import annotations

from rendobar._client import _Deprecations, _parse_deprecation, _route_of
from rendobar._plumbing import Fetched as _Fetched


def response(value: str) -> _Fetched[bytes]:
    return _Fetched({"deprecation": value}, b"")


def test_a_handler_that_raises_does_not_escape() -> None:
    def broken(_notice: object) -> None:
        raise RuntimeError("logger down")

    _Deprecations(broken).note(response("@1784851200"), "GET", "/jobs/job_1/metrics")


def test_a_value_no_date_can_hold_is_ignored() -> None:
    assert _parse_deprecation("@99999999999999999999") is None
    seen: list = []
    _Deprecations(seen.append).note(response("@99999999999999999999"), "GET", "/jobs/job_1")
    assert seen == []


def test_one_notice_per_route_across_ids() -> None:
    seen: list = []
    tracker = _Deprecations(seen.append)
    for job_id in ("job_1", "job_2", "job_3"):
        tracker.note(response("@1784851200"), "GET", f"/jobs/{job_id}/metrics")
    assert len(seen) == 1 and seen[0].path == "/jobs/job_1/metrics"


def test_route_of_keeps_static_segments() -> None:
    assert _route_of("/jobs/job_abc/metrics?x=1") == "/jobs/:id/metrics"
    assert _route_of("/billing/checkout/pro") == "/billing/checkout/pro"

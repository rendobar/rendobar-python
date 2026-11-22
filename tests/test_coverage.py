"""Every operation in fern/openapi.json is reachable from the public client, or skipped on purpose.

Nothing here lists which method calls which operation. Each public method of
`Rendobar` and `AsyncRendobar` runs once over a recording transport, and the
requests it sends are matched to the spec's operations. An operation that no
method requests, and that `SKIP` does not name, fails with its name. So does a
`SKIP` entry the client does reach, or one the spec no longer has.

The calls come from `test_resources.CASES` (one per resource method) plus the
job lifecycle, uploads and account below. A public method with no call fails.
"""
from __future__ import annotations

import inspect
import io
import re
from typing import Any, Callable, Dict, List, Set, Tuple

import httpx
import pytest

from rendobar import AsyncRendobar, Rendobar, RendobarError
from test_resources import CASES, SPEC, make, run, synth

LATER = "not in this release (nor in @rendobar/sdk); a later minor adds it"
DEPRECATED = "deprecated in the spec, replaced by the operation the client calls instead"

# "METHOD /path": why the public client does not call it.
SKIP: Dict[str, str] = {
    "GET /jobs/{id}/resources": LATER,
    "GET /jobs/{id}/metrics": DEPRECATED + " (GET /jobs/{id}/resources)",
    "GET /jobs/{id}/throughput": LATER,
    "POST /jobs/{id}/share": LATER,
    "GET /jobs/{id}/share": LATER,
    "DELETE /jobs/{id}/share": LATER,
    "POST /jobs/{id}/dispute": "a charge dispute is a person's call, made in the dashboard",
    "GET /models": LATER,
    "POST /billing/checkout/pro": DEPRECATED + " (billing.checkout_plan(\"pro\")); a new SDK ships no deprecated alias",
    "GET /billing/history/{id}/pdf": LATER,
    "GET /billing/history/{id}/receipt": LATER,
    "POST /orgs/current/exit-feedback": "the dashboard's delete-workspace survey",
    "GET /orgs/current/callback-secret": LATER,
    "POST /orgs/current/callback-secret/rotate": LATER,
    "GET /orgs/current/audit-log": LATER,
    "POST /orgs/current/invitations": LATER,
    "POST /orgs/current/invitations/{invitationId}/resend": LATER,
    "GET /invitations/{id}/preview": "auth flow: what an invitee sees before signing in",
    "GET /assets/{id}/content": "a browser redirect to the file; assets.download returns the same URL",
    "GET /assets/{id}/preview": "the dashboard's thumbnail PNG",
    "POST /team/invite": DEPRECATED + " (orgs.members.invite)",
    "PATCH /team/role": DEPRECATED + " (orgs.members.change_role)",
    "POST /team/remove": DEPRECATED + " (orgs.members.remove)",
    "POST /team/revoke-invitation": DEPRECATED + " (orgs.invitations.revoke)",
    "GET /upload-sessions/{token}": "MCP upload page: authed by the session token, not an API key",
    "POST /upload-sessions/{token}/files": "MCP upload page: authed by the session token, not an API key",
    "POST /upload-sessions/{token}/files/{assetId}/complete": "MCP upload page: authed by the session token, not an API key",
    "POST /upload-sessions/{token}/done": "MCP upload page: authed by the session token, not an API key",
}

# Public resources that send no request in the HTTP spec.
NOT_HTTP = {"realtime": "a WebSocket stream, not an operation in the HTTP spec"}


def _first(items: Any) -> Any:
    """The first item of a sync or async iterator: list_all pages on, and one page is enough here."""
    if hasattr(items, "__anext__"):
        return items.__anext__()
    return next(iter(items))


# The methods test_resources.CASES leaves out, each called the shortest way that sends its requests.
LIFECYCLE: Dict[str, Callable[[Any], Any]] = {
    "jobs.create": lambda rb: rb.jobs.create({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}}),
    "jobs.run": lambda rb: rb.jobs.run({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}}, timeout=0),
    "jobs.wait": lambda rb: rb.jobs.wait("job_1", timeout=0),
    "jobs.get": lambda rb: rb.jobs.get("job_1"),
    "jobs.list": lambda rb: rb.jobs.list(),
    "jobs.list_all": lambda rb: _first(rb.jobs.list_all()),
    "jobs.cancel": lambda rb: rb.jobs.cancel("job_1"),
    "jobs.download": lambda rb: rb.jobs.download("job_1", io.BytesIO()),
    "jobs.types": lambda rb: rb.jobs.types(),
    "jobs.schema": lambda rb: rb.jobs.schema("ffprobe"),
    "uploads.create": lambda rb: rb.uploads.create(b"bytes", filename="clip.mp4", content_type="video/mp4"),
    "account.capabilities": lambda rb: rb.account.capabilities(),
}
CALLS: Dict[str, Callable[[Any], Any]] = {**{name: case.call for name, case in CASES.items()}, **LIFECYCLE}

# The answer that leads a multi-step call to its next request: a fresh upload, not a deduplicated one.
STATUS = {"createAsset": "201"}


# ── the spec's operations ─────────────────────────────────────────────

def _operations() -> Dict[str, Tuple[str, "re.Pattern[str]", Dict[str, Any]]]:
    """'METHOD /path' -> (operationId, the path as a regex, the operation)."""
    out: Dict[str, Tuple[str, re.Pattern[str], Dict[str, Any]]] = {}
    for path, item in SPEC["paths"].items():
        pattern = re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", path) + "$")
        for method, op in item.items():
            if method in ("get", "post", "put", "patch", "delete"):
                out[f"{method.upper()} {path}"] = (op["operationId"], pattern, op)
    return out


OPERATIONS = _operations()


def _match(method: str, path: str) -> str:
    """The operation a request is: the most literal template that fits (/jobs/stats before /jobs/{id})."""
    fits = [key for key, (_, pattern, _) in OPERATIONS.items() if key.split(" ")[0] == method and pattern.match(path)]
    if not fits:
        raise AssertionError(f"{method} {path} is not an operation in fern/openapi.json")
    return min(fits, key=lambda key: key.count("{"))


def _answer(key: str) -> httpx.Response:
    op_id, _, op = OPERATIONS[key]
    status = STATUS.get(op_id) or next(code for code in ("200", "201", "204") if code in op["responses"])
    schema = op["responses"][status].get("content", {}).get("application/json", {}).get("schema")
    if schema is None:
        return httpx.Response(int(status))
    return httpx.Response(int(status), json=synth(schema))


# ── which operations the public client reaches ────────────────────────

def public_methods(client: object) -> Set[str]:
    """Every public method of every resource on the client, nested ones (orgs.members) included."""
    found: Set[str] = set()

    def resources(target: object) -> Dict[str, object]:
        return {attr: value for attr, value in vars(target).items()
                if not attr.startswith("_") and attr not in NOT_HTTP and type(value).__module__.startswith("rendobar.")}

    def walk(target: object, prefix: str) -> None:
        for attr, value in resources(target).items():
            walk(value, f"{prefix}{attr}.")
        for attr in dir(type(target)):
            if not attr.startswith("_") and inspect.isfunction(getattr(type(target), attr)):
                found.add(f"{prefix}{attr}")

    for attr, resource in resources(client).items():
        walk(resource, f"{attr}.")
    return found


def reached(mode: str) -> Dict[str, Set[str]]:
    """'METHOD /path' -> the public methods that request it, observed over the transport."""
    out: Dict[str, Set[str]] = {}
    for name, call in CALLS.items():
        seen: List[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host != "api.test":  # a presigned upload URL: storage, not the API
                return httpx.Response(200, headers={"ETag": '"etag"'})
            key = _match(request.method, request.url.path)
            seen.append(key)
            return _answer(key)

        try:
            run(call(make(mode, handler, max_retries=0)))
        except RendobarError:
            pass  # a wait that times out, or a synthesized answer a model refuses: the request was still sent
        assert seen, f"{name} sent no request"
        for key in seen:
            out.setdefault(key, set()).add(name)
    return out


MODES = ["sync", "async"]
REACHED = {mode: reached(mode) for mode in MODES}


def test_every_public_method_is_exercised() -> None:
    for client in (Rendobar("rb_k"), AsyncRendobar("rb_k")):
        methods = public_methods(client)
        assert methods - set(CALLS) == set(), "public methods with no call in test_coverage.LIFECYCLE or test_resources.CASES"
        assert set(CALLS) - methods == set(), "calls for methods the client no longer has"


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("key", sorted(OPERATIONS))
def test_every_operation_is_reachable_or_skipped(key: str, mode: str) -> None:
    op_id = OPERATIONS[key][0]
    methods = REACHED[mode].get(key)
    if key in SKIP:
        assert methods is None, f"{op_id} ({key}) is in SKIP but {mode} {sorted(methods or ())} requests it: drop the entry"
    else:
        assert methods, f"{op_id} ({key}) is reachable from no public {mode} method: add one, or a SKIP entry with the reason"


def test_every_skip_entry_is_in_the_spec() -> None:
    assert set(SKIP) - set(OPERATIONS) == set(), "SKIP names operations fern/openapi.json no longer has"

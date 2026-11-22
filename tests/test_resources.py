"""Every resource method beyond the job lifecycle, on the sync and the async client.

Each case states the request the method must send (method, path, query, JSON
body) and the public model it must return. The response is synthesized from
the operation's own response schema in fern/openapi.json, the spec the core is
generated from, so a model that stops reading what the spec says fails here.
No mock server: the HTTP side is an httpx.MockTransport.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from urllib.parse import parse_qsl

import httpx
import pytest

import rendobar
from rendobar import (
    AccountBuckets,
    ApiKey,
    ApiKeyRevoked,
    Asset,
    AssetDeleted,
    AssetDownload,
    AsyncRendobar,
    AuthenticationError,
    BillingPortal,
    BillingState,
    ClientUsage,
    ComposeEffects,
    ComposeEngineEffects,
    ComposeInvalid,
    ComposeValid,
    CreatedApiKey,
    CreditsCheckout,
    CurrentOrg,
    DefaultPaymentMethod,
    DeliveriesPageMeta,
    DeliveriesRetried,
    InternalServerError,
    InvalidArgumentError,
    Invitation,
    InvitationRevoked,
    Invoice,
    JobLogEntry,
    JobStats,
    JobTimings,
    ListMeta,
    MemberRemoved,
    MemberRoleChanged,
    NewOrganization,
    NotFoundError,
    Notification,
    NotificationsMeta,
    NotificationsRead,
    OffsetPageMeta,
    Organization,
    OrgMembership,
    OrgSettings,
    Page,
    PageMeta,
    PaymentMethod,
    PermissionDeniedError,
    PlanChanged,
    PlanCheckoutStarted,
    PreparedAwsStorage,
    RateLimitError,
    Rendobar,
    RendobarError,
    ResponseValidationError,
    RetriedDelivery,
    S3BucketLookup,
    StorageActivity,
    StorageConnection,
    StorageObjects,
    StorageTestResult,
    Subscription,
    SupabaseBuckets,
    SupabaseProjects,
    SupabaseSignIn,
    Transaction,
    UploadProgress,
    UsageSummary,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEndpointWithSecret,
    WebhookTestResult,
)

SPEC = json.loads((Path(__file__).resolve().parent.parent / "fern" / "openapi.json").read_text(encoding="utf-8"))


# ── responses synthesized from the spec ───────────────────────────────

def _resolve(schema: Dict[str, Any]) -> Dict[str, Any]:
    if "$ref" in schema:
        resolved: Dict[str, Any] = SPEC["components"]["schemas"][schema["$ref"].split("/")[-1]]
        return resolved
    return schema


def synth(schema: Dict[str, Any], key: str = "", depth: int = 0) -> Any:
    """A value the schema says is valid: its example, its first enum value or variant, or a typed placeholder."""
    if depth > 12:
        return {}
    schema = _resolve(schema)
    if "example" in schema:
        return schema["example"]
    for union in ("oneOf", "anyOf"):
        if union in schema:
            return synth(schema[union][0], key, depth + 1)
    if "allOf" in schema:
        out: Dict[str, Any] = {}
        for part in schema["allOf"]:
            value = synth(part, key, depth + 1)
            if isinstance(value, dict):
                out.update(value)
        return out
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "null")
    if kind == "object" or "properties" in schema:
        return {name: synth(sub, name, depth + 1) for name, sub in schema.get("properties", {}).items()}
    if kind == "array":
        return [synth(schema.get("items", {}), key, depth + 1)]
    if kind == "integer":
        return 1731000000000 if key.endswith("At") else 1
    if kind == "number":
        return 1  # a whole number is a valid JSON number, and in range for a 0..1 fraction
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    if kind == "string":
        return "https://cdn.test/x" if key.lower().endswith("url") else f"{key or 'value'}"
    return {}


def _operation(op_id: str) -> Dict[str, Any]:
    for item in SPEC["paths"].values():
        for op in item.values():
            if isinstance(op, dict) and op.get("operationId") == op_id:
                return op
    raise KeyError(op_id)


def answer(op_id: str) -> Tuple[int, Any]:
    """The operation's first success status and a body its response schema allows."""
    op = _operation(op_id)
    for code in ("200", "201", "204"):
        if code in op["responses"]:
            schema = op["responses"][code].get("content", {}).get("application/json", {}).get("schema")
            return int(code), (synth(schema) if schema else None)
    raise KeyError(f"{op_id} has no success response")


# ── the clients over a MockTransport ──────────────────────────────────

@dataclass
class Sent:
    method: str
    path: str
    query: Dict[str, str]
    body: Any
    headers: httpx.Headers


@dataclass
class Recorder:
    """Answers each request with `respond` and keeps what was sent."""

    respond: Callable[[httpx.Request], httpx.Response]
    sent: List[Sent] = field(default_factory=lambda: [])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        content = request.read()
        self.sent.append(Sent(request.method, request.url.raw_path.decode().split("?")[0], dict(parse_qsl(request.url.query.decode())),
                              json.loads(content) if content else None, request.headers))
        return self.respond(request)


def _install(http: Any, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    http._transport = httpx.MockTransport(handler)
    http._mounts = {}


def make(mode: str, handler: Callable[[httpx.Request], httpx.Response], **kw: Any) -> Union[Rendobar, AsyncRendobar]:
    client: Union[Rendobar, AsyncRendobar] = (Rendobar if mode == "sync" else AsyncRendobar)("rb_k", base_url="https://api.test", **kw)
    _install(client._core._client_wrapper.httpx_client.httpx_client, handler)  # noqa: SLF001
    return client


def run(value: Any) -> Any:
    """The call's result: awaited for the async client."""
    if inspect.isawaitable(value):
        async def wait() -> Any:
            return await value
        return asyncio.run(wait())
    return value


def json_response(status: int, body: Any) -> Callable[[httpx.Request], httpx.Response]:
    def respond(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status, headers={"x-request-id": "req_unit"})
        return httpx.Response(status, json=body, headers={"x-request-id": "req_unit"})
    return respond


# ── one case per method ───────────────────────────────────────────────

@dataclass
class Case:
    call: Callable[[Any], Any]
    method: str
    path: str
    op: str
    returns: Union[Type[object], Tuple[Type[object], ...], None]
    query: Dict[str, str] = field(default_factory=lambda: {})
    body: Any = None
    item: Optional[Type[object]] = None  # for a list or a Page: each item's type
    meta: Optional[Type[object]] = None  # for a Page: its meta's type


CASES: Dict[str, Case] = {
    # jobs, beyond the lifecycle
    "jobs.retry_deliveries": Case(lambda rb: rb.jobs.retry_deliveries("job_1"), "POST", "/jobs/job_1/deliveries/retry", "retryDeliveries", DeliveriesRetried),
    "jobs.logs": Case(lambda rb: rb.jobs.logs("job_1"), "GET", "/jobs/job_1/logs", "getJobLogs", list, item=JobLogEntry),
    "jobs.get_timings": Case(lambda rb: rb.jobs.get_timings("job_1"), "GET", "/jobs/job_1/timings", "getJobTimings", JobTimings),
    "jobs.stats": Case(lambda rb: rb.jobs.stats(window="7d"), "GET", "/jobs/stats", "getJobStats", JobStats, query={"window": "7d"}),
    # billing
    "billing.state": Case(lambda rb: rb.billing.state(), "GET", "/billing/state", "getBillingState", BillingState),
    "billing.usage": Case(lambda rb: rb.billing.usage(start="2026-11-01", end="2026-11-30"), "GET", "/billing/usage", "getUsage",
                          UsageSummary, query={"start": "2026-11-01", "end": "2026-11-30"}),
    "billing.usage_by_client": Case(lambda rb: rb.billing.usage_by_client(days=7), "GET", "/billing/usage-by-client", "getUsageByClient",
                                    list, query={"days": "7"}, item=ClientUsage),
    "billing.transactions": Case(lambda rb: rb.billing.transactions(page=2, limit=10), "GET", "/billing/transactions", "listTransactions",
                                 Page, query={"page": "2", "limit": "10"}, item=Transaction, meta=PageMeta),
    "billing.history": Case(lambda rb: rb.billing.history(), "GET", "/billing/history", "listInvoices", Page, item=Invoice, meta=PageMeta),
    "billing.checkout_credits": Case(lambda rb: rb.billing.checkout_credits(25, interval="month"), "POST", "/billing/checkout/credits",
                                     "createCreditsCheckout", CreditsCheckout, body={"amount": 25, "interval": "month"}),
    "billing.checkout_plan": Case(lambda rb: rb.billing.checkout_plan("pro"), "POST", "/billing/checkout/plan", "createPlanCheckout",
                                  (PlanCheckoutStarted, PlanChanged), body={"plan": "pro"}),
    "billing.cancel_subscription": Case(lambda rb: rb.billing.cancel_subscription(), "PATCH", "/billing/subscription",
                                        "updateSubscription", Subscription, body={"cancelAtPeriodEnd": True}),
    "billing.reactivate_subscription": Case(lambda rb: rb.billing.reactivate_subscription(), "PATCH", "/billing/subscription",
                                            "updateSubscription", Subscription, body={"cancelAtPeriodEnd": False}),
    "billing.cancel_credit_schedule": Case(lambda rb: rb.billing.cancel_credit_schedule(), "DELETE", "/billing/credit-schedule",
                                           "cancelCreditSchedule", None),
    "billing.payment_methods": Case(lambda rb: rb.billing.payment_methods(), "GET", "/billing/payment-methods", "listPaymentMethods",
                                    list, item=PaymentMethod),
    "billing.delete_payment_method": Case(lambda rb: rb.billing.delete_payment_method("pm_1"), "DELETE", "/billing/payment-methods/pm_1",
                                          "deletePaymentMethod", None),
    "billing.set_default_payment_method": Case(lambda rb: rb.billing.set_default_payment_method("pm_1"), "PATCH",
                                               "/billing/payment-methods/pm_1/default", "setDefaultPaymentMethod", DefaultPaymentMethod),
    "billing.portal_url": Case(lambda rb: rb.billing.portal_url(), "GET", "/billing/payment-methods/portal-url", "getBillingPortalUrl",
                               BillingPortal),
    # assets
    "assets.list": Case(lambda rb: rb.assets.list(kind="media", status="ready", lifecycle="persisted", limit=5, offset=10), "GET", "/assets",
                        "listAssets", Page, query={"kind": "media", "status": "ready", "lifecycle": "persisted", "limit": "5", "offset": "10"},
                        item=Asset, meta=OffsetPageMeta),
    "assets.get": Case(lambda rb: rb.assets.get("asset_1"), "GET", "/assets/asset_1", "getAsset", Asset),
    "assets.delete": Case(lambda rb: rb.assets.delete("asset_1"), "DELETE", "/assets/asset_1", "deleteAsset", AssetDeleted),
    "assets.download": Case(lambda rb: rb.assets.download("asset_1"), "GET", "/assets/asset_1/download", "downloadAsset", AssetDownload),
    "assets.templates": Case(lambda rb: rb.assets.templates(limit=3), "GET", "/assets/templates", "listAssetTemplates", Page,
                             query={"limit": "3"}, item=Asset, meta=OffsetPageMeta),
    # webhook endpoints and deliveries
    "webhooks.create": Case(lambda rb: rb.webhooks.create(name="hook", url="https://example.com/h", subscribed_events=["job.completed"]),
                            "POST", "/webhooks/endpoints", "createWebhookEndpoint", WebhookEndpointWithSecret,
                            body={"name": "hook", "url": "https://example.com/h", "subscribedEvents": ["job.completed"]}),
    "webhooks.list": Case(lambda rb: rb.webhooks.list(), "GET", "/webhooks/endpoints", "listWebhookEndpoints", Page,
                          item=WebhookEndpoint, meta=ListMeta),
    "webhooks.get": Case(lambda rb: rb.webhooks.get("whe_1"), "GET", "/webhooks/endpoints/whe_1", "getWebhookEndpoint", WebhookEndpoint),
    "webhooks.update": Case(lambda rb: rb.webhooks.update("whe_1", name="renamed", active=False), "PATCH", "/webhooks/endpoints/whe_1",
                            "updateWebhookEndpoint", WebhookEndpoint, body={"name": "renamed", "active": False}),
    "webhooks.delete": Case(lambda rb: rb.webhooks.delete("whe_1"), "DELETE", "/webhooks/endpoints/whe_1", "deleteWebhookEndpoint", None),
    "webhooks.rotate_secret": Case(lambda rb: rb.webhooks.rotate_secret("whe_1"), "POST", "/webhooks/endpoints/whe_1/secret",
                                   "rotateWebhookSecret", WebhookEndpointWithSecret),
    "webhooks.test": Case(lambda rb: rb.webhooks.test("whe_1"), "POST", "/webhooks/endpoints/whe_1/test", "testWebhookEndpoint",
                          WebhookTestResult),
    "webhooks.list_deliveries": Case(lambda rb: rb.webhooks.list_deliveries(endpoint_id="whe_1", status="failed", job_id="job_1", limit=5),
                                     "GET", "/webhooks/deliveries", "listWebhookDeliveries", Page,
                                     query={"endpointId": "whe_1", "status": "failed", "jobId": "job_1", "limit": "5"},
                                     item=WebhookDelivery, meta=DeliveriesPageMeta),
    "webhooks.retry_delivery": Case(lambda rb: rb.webhooks.retry_delivery("whd_1"), "POST", "/webhooks/deliveries/whd_1/retry",
                                    "retryWebhookDelivery", RetriedDelivery),
    # storage
    "storage.create": Case(lambda rb: rb.storage.create({"provider": "s3", "id": "media", "bucket": "b", "region": "us-east-1",
                                                         "credentials": {"type": "keys", "access_key_id": "AK", "secret_access_key": "SK"}}),
                           "POST", "/storage", "createStorage", StorageConnection,
                           body={"provider": "s3", "id": "media", "bucket": "b", "region": "us-east-1",
                                 "credentials": {"type": "keys", "accessKeyId": "AK", "secretAccessKey": "SK"}}),
    "storage.list": Case(lambda rb: rb.storage.list(), "GET", "/storage", "listStorage", Page, item=StorageConnection, meta=ListMeta),
    "storage.get": Case(lambda rb: rb.storage.get("media"), "GET", "/storage/media", "getStorage", StorageConnection),
    "storage.update": Case(lambda rb: rb.storage.update("media", credentials={"type": "keys", "access_key_id": "AK", "secret_access_key": "SK"},
                                                        on_conflict="replace"),
                           "PATCH", "/storage/media", "updateStorage", StorageConnection,
                           body={"credentials": {"type": "keys", "accessKeyId": "AK", "secretAccessKey": "SK"}, "onConflict": "replace"}),
    "storage.delete": Case(lambda rb: rb.storage.delete("media"), "DELETE", "/storage/media", "deleteStorage", None),
    "storage.test": Case(lambda rb: rb.storage.test("media"), "POST", "/storage/media/test", "testStorage", StorageTestResult),
    "storage.stats": Case(lambda rb: rb.storage.stats("media"), "GET", "/storage/media/stats", "getStorageStats", StorageActivity),
    "storage.list_objects": Case(lambda rb: rb.storage.list_objects("media", prefix="", cursor="c2", limit=10), "GET", "/storage/media/objects",
                                 "listStorageObjects", StorageObjects, query={"cursor": "c2", "limit": "10"}),
    "storage.prepare_aws": Case(lambda rb: rb.storage.prepare_aws(id="media", bucket="b", region="eu-central-1"), "POST", "/storage/aws/prepare",
                                "prepareAwsStorage", PreparedAwsStorage, body={"id": "media", "bucket": "b", "region": "eu-central-1"}),
    "storage.list_account_buckets": Case(lambda rb: rb.storage.list_account_buckets(provider="r2"), "GET", "/storage/buckets",
                                         "listAccountBuckets", AccountBuckets, query={"provider": "r2"}),
    "storage.look_up_s3_bucket": Case(lambda rb: rb.storage.look_up_s3_bucket("my-bucket"), "GET", "/storage/s3/bucket", "lookUpS3Bucket",
                                      S3BucketLookup, query={"name": "my-bucket"}),
    "storage.start_supabase": Case(lambda rb: rb.storage.start_supabase(), "POST", "/storage/supabase/start", "startSupabaseStorage",
                                   SupabaseSignIn),
    "storage.list_supabase_projects": Case(lambda rb: rb.storage.list_supabase_projects("st_1"), "GET", "/storage/supabase/sessions/st_1",
                                           "getSupabaseSession", SupabaseProjects),
    "storage.list_supabase_buckets": Case(lambda rb: rb.storage.list_supabase_buckets("st_1", "abcdefghijklmnopqrst"), "GET",
                                          "/storage/supabase/sessions/st_1/projects/abcdefghijklmnopqrst/buckets", "listSupabaseBuckets",
                                          SupabaseBuckets),
    "storage.finish_supabase": Case(lambda rb: rb.storage.finish_supabase(state="st_1", project_ref="ref", id="media", bucket="b"), "POST",
                                    "/storage/supabase/finish", "finishSupabaseStorage", StorageConnection,
                                    body={"state": "st_1", "projectRef": "ref", "id": "media", "bucket": "b"}),
    # API keys
    "api_keys.create": Case(lambda rb: rb.api_keys.create(name="ci", expires_in=3600, scopes=["jobs:read"]), "POST", "/api-keys",
                            "createApiKey", CreatedApiKey, body={"name": "ci", "expiresIn": 3600, "scopes": ["jobs:read"]}),
    "api_keys.list": Case(lambda rb: rb.api_keys.list(), "GET", "/api-keys", "listApiKeys", list, item=ApiKey),
    "api_keys.revoke": Case(lambda rb: rb.api_keys.revoke("key_1"), "DELETE", "/api-keys/key_1", "revokeApiKey", ApiKeyRevoked),
    "api_keys.update": Case(lambda rb: rb.api_keys.update("key_1", enabled=False), "PATCH", "/api-keys/key_1", "updateApiKey", ApiKey,
                            body={"enabled": False}),
    # organizations
    "orgs.list": Case(lambda rb: rb.orgs.list(), "GET", "/orgs", "listOrgs", list, item=OrgMembership),
    "orgs.current": Case(lambda rb: rb.orgs.current(), "GET", "/orgs/current", "getCurrentOrg", CurrentOrg),
    "orgs.create": Case(lambda rb: rb.orgs.create(name="Acme", slug="acme"), "POST", "/orgs", "createOrg", NewOrganization,
                        body={"name": "Acme", "slug": "acme"}),
    "orgs.update": Case(lambda rb: rb.orgs.update(name="Acme 2"), "PATCH", "/orgs/current", "updateOrg", Organization, body={"name": "Acme 2"}),
    "orgs.delete": Case(lambda rb: rb.orgs.delete(), "DELETE", "/orgs/current", "deleteOrg", None),
    "orgs.get_settings": Case(lambda rb: rb.orgs.get_settings(), "GET", "/orgs/current/settings", "getOrgSettings", OrgSettings),
    "orgs.update_settings": Case(lambda rb: rb.orgs.update_settings(billing_emails_enabled=False, default_region="eu-central-1"), "PATCH",
                                 "/orgs/current/settings", "updateOrgSettings", OrgSettings,
                                 body={"billingEmailsEnabled": False, "defaultRegion": "eu-central-1"}),
    "orgs.members.invite": Case(lambda rb: rb.orgs.members.invite(email="a@example.com", role="member"), "POST", "/orgs/current/members",
                                "inviteOrgMember", Invitation, body={"email": "a@example.com", "role": "member"}),
    "orgs.members.change_role": Case(lambda rb: rb.orgs.members.change_role("mem_1", role="admin"), "PATCH", "/orgs/current/members/mem_1",
                                     "updateOrgMemberRole", MemberRoleChanged, body={"role": "admin"}),
    "orgs.members.remove": Case(lambda rb: rb.orgs.members.remove("mem_1"), "DELETE", "/orgs/current/members/mem_1", "removeOrgMember",
                                MemberRemoved),
    "orgs.invitations.revoke": Case(lambda rb: rb.orgs.invitations.revoke("inv_1"), "DELETE", "/orgs/current/invitations/inv_1",
                                    "revokeOrgInvitation", InvitationRevoked),
    # compose
    "compose.effects": Case(lambda rb: rb.compose.effects(), "GET", "/compose/effects", "listComposeEffects", ComposeEffects),
    "compose.engine_effects": Case(lambda rb: rb.compose.engine_effects(), "GET", "/compose/effects/engine", "listComposeEngineEffects",
                                   ComposeEngineEffects),
    "compose.validate": Case(lambda rb: rb.compose.validate({"width": 1280, "tracks": []}), "POST", "/compose/validate", "validateCompose",
                             (ComposeValid, ComposeInvalid), body={"params": {"width": 1280, "tracks": []}}),
    # notifications
    "notifications.list": Case(lambda rb: rb.notifications.list(), "GET", "/notifications", "listNotifications", Page,
                               item=Notification, meta=NotificationsMeta),
    "notifications.mark_read": Case(lambda rb: rb.notifications.mark_read(["ntf_1", "ntf_2"]), "POST", "/notifications/read",
                                    "markNotificationsRead", NotificationsRead, body={"ids": ["ntf_1", "ntf_2"]}),
}

MODES = ["sync", "async"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("name", sorted(CASES))
def test_each_method_sends_its_request_and_reads_its_model(name: str, mode: str) -> None:
    case = CASES[name]
    status, payload = answer(case.op)
    recorder = Recorder(json_response(status, payload))
    result = run(case.call(make(mode, recorder)))

    assert len(recorder.sent) == 1
    sent = recorder.sent[0]
    assert (sent.method, sent.path) == (case.method, case.path)
    assert sent.query == case.query
    if case.body is not None:
        assert sent.body == case.body
    elif sent.method in ("GET", "DELETE"):
        assert sent.body is None
    if case.returns is None:
        assert result is None
    else:
        assert isinstance(result, case.returns)
    if case.item is not None:
        items = result.data if isinstance(result, Page) else result
        assert isinstance(items, list) and items and all(isinstance(item, case.item) for item in items)
    if case.meta is not None:
        assert isinstance(result, Page) and isinstance(result.meta, case.meta)


def test_every_resource_method_has_a_case() -> None:
    """The cases above are the surface: a public method added without one fails here."""
    lifecycle = {"create", "get", "list", "list_all", "wait", "run", "cancel", "download", "types", "schema"}
    found = set()
    for resource in ("jobs", "billing", "assets", "webhooks", "storage", "api_keys", "orgs", "compose", "notifications"):
        target = getattr(Rendobar("rb_k"), resource)
        for attr in dir(target):
            if not attr.startswith("_") and callable(getattr(target, attr)):
                found.add(f"{resource}.{attr}")
    for nested in ("members", "invitations"):
        target = getattr(Rendobar("rb_k").orgs, nested)
        found |= {f"orgs.{nested}.{attr}" for attr in dir(target) if not attr.startswith("_") and callable(getattr(target, attr))}
    found -= {f"jobs.{name}" for name in lifecycle}
    assert found == set(CASES)


def test_the_sync_and_async_clients_have_the_same_methods() -> None:
    def surface(client: object) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for resource in ("jobs", "account", "billing", "uploads", "assets", "webhooks", "storage", "api_keys", "orgs", "compose",
                         "notifications", "realtime"):
            target = getattr(client, resource)
            out[resource] = sorted(a for a in dir(target) if not a.startswith("_") and callable(getattr(target, a)))
        for nested in ("members", "invitations"):
            target = getattr(getattr(client, "orgs"), nested)
            out[f"orgs.{nested}"] = sorted(a for a in dir(target) if not a.startswith("_") and callable(getattr(target, a)))
        return out

    sync, asynchronous = surface(Rendobar("rb_k")), surface(AsyncRendobar("rb_k"))
    assert sync == asynchronous
    for resource, names in sync.items():
        for method in names:
            target_sync = Rendobar("rb_k")
            target_async = AsyncRendobar("rb_k")
            for part in resource.split("."):
                target_sync, target_async = getattr(target_sync, part), getattr(target_async, part)
            sig_sync = inspect.signature(getattr(target_sync, method))
            sig_async = inspect.signature(getattr(target_async, method))
            assert list(sig_sync.parameters) == list(sig_async.parameters), f"{resource}.{method}"


# ── reading: one model per resource, tolerant of a newer API ──────────

@pytest.mark.parametrize("mode", MODES)
def test_get_list_and_update_return_the_same_storage_class(mode: str) -> None:
    connection = answer("getStorage")[1]["data"]
    pages = {
        "GET /storage/media": (200, {"data": connection}),
        "PATCH /storage/media": (200, {"data": connection}),
        "GET /storage": (200, {"data": [connection], "meta": {"total": 1}}),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        code, payload = pages[f"{request.method} {request.url.path}"]
        return httpx.Response(code, json=payload)

    rb = make(mode, Recorder(respond))
    got, updated, listed = run(rb.storage.get("media")), run(rb.storage.update("media", public_base_url="https://cdn.test")), run(rb.storage.list())
    assert type(got) is type(updated) is type(listed.data[0]) is StorageConnection
    assert StorageConnection.__name__ == "StorageConnection"


@pytest.mark.parametrize("mode", MODES)
def test_a_newer_enum_value_and_an_unknown_field_still_parse(mode: str) -> None:
    status, payload = answer("listWebhookDeliveries")
    payload["data"][0]["status"] = "bounced"  # a delivery status newer than this SDK
    payload["data"][0]["brandNewField"] = {"added": "later"}
    page = run(make(mode, Recorder(json_response(status, payload))).webhooks.list_deliveries())
    delivery = page.data[0]
    assert delivery.status == "bounced"
    assert delivery.model_extra is not None and delivery.model_extra["brandNewField"] == {"added": "later"}


@pytest.mark.parametrize("mode", MODES)
def test_a_body_that_is_not_the_model_is_a_response_validation_error(mode: str) -> None:
    for body in ({"data": {"unexpected": True}}, {"nodata": 1}, "<html>proxy</html>"):
        def respond(request: httpx.Request, body: Any = body) -> httpx.Response:
            if isinstance(body, str):
                return httpx.Response(200, text=body, headers={"x-request-id": "req_bad"})
            return httpx.Response(200, json=body, headers={"x-request-id": "req_bad"})

        with pytest.raises(ResponseValidationError) as info:
            run(make(mode, Recorder(respond)).webhooks.get("whe_1"))
        assert info.value.status_code == 200


@pytest.mark.parametrize("mode", MODES)
def test_compose_validate_returns_the_problems_variant(mode: str) -> None:
    invalid = {"data": {"valid": False, "problems": [{"path": ["tracks", 0], "message": "Empty track"}], "upgraded": [], "warnings": []}}
    result = run(make(mode, Recorder(json_response(200, invalid))).compose.validate({"tracks": [{}]}))
    assert isinstance(result, ComposeInvalid) and result.problems[0].message == "Empty track"


@pytest.mark.parametrize("mode", MODES)
def test_checkout_plan_reads_a_plan_changed_in_place(mode: str) -> None:
    changed = {"data": {"kind": "changed", "plan": "studio"}}
    result = run(make(mode, Recorder(json_response(200, changed))).billing.checkout_plan("studio"))
    assert isinstance(result, PlanChanged) and result.plan == "studio"


# ── writing: only what was passed ─────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
def test_an_update_sends_only_the_fields_passed(mode: str) -> None:
    answers = {"/webhooks/endpoints/whe_1": answer("updateWebhookEndpoint"), "/orgs/current/settings": answer("updateOrgSettings")}
    recorder = Recorder(lambda request: json_response(*answers[request.url.path])(request))
    rb = make(mode, recorder)
    run(rb.webhooks.update("whe_1", url="https://example.com/new"))
    run(rb.orgs.update_settings(region_pinned=True))
    assert recorder.sent[0].body == {"url": "https://example.com/new"}
    assert recorder.sent[1].body == {"regionPinned": True}


# ── failures ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
def test_a_404_is_not_found_with_the_request_id(mode: str) -> None:
    respond = json_response(404, {"error": {"code": "NOT_FOUND", "message": "Endpoint not found"}})
    with pytest.raises(NotFoundError) as info:
        run(make(mode, Recorder(respond)).webhooks.get("whe_missing"))
    assert info.value.code == "NOT_FOUND" and info.value.request_id == "req_unit"


@pytest.mark.parametrize("mode", MODES)
def test_a_missing_scope_is_permission_denied(mode: str) -> None:
    respond = json_response(403, {"error": {"code": "INSUFFICIENT_SCOPE", "message": "Needs keys:write"}})
    with pytest.raises(PermissionDeniedError) as info:
        run(make(mode, Recorder(respond)).api_keys.create(name="x"))
    assert info.value.code == "INSUFFICIENT_SCOPE"


@pytest.mark.parametrize("mode", MODES)
def test_a_write_is_not_retried_after_a_5xx_but_a_read_is(mode: str) -> None:
    recorder = Recorder(json_response(503, {"error": {"code": "INTERNAL_ERROR", "message": "busy"}}))
    rb = make(mode, recorder, max_retries=2)
    with pytest.raises(InternalServerError):
        run(rb.webhooks.create(name="hook", url="https://example.com/h", subscribed_events=["job.completed"]))
    assert len(recorder.sent) == 1  # it may have been created: never twice
    recorder.sent.clear()
    with pytest.raises(InternalServerError):
        run(rb.webhooks.list())
    assert len(recorder.sent) == 3  # a read is safe to repeat


@pytest.mark.parametrize("mode", MODES)
def test_a_write_is_retried_after_a_429(mode: str) -> None:
    status, payload = answer("createWebhookEndpoint")
    replies = [httpx.Response(429, json={"error": {"code": "RATE_LIMITED", "message": "slow"}}, headers={"Retry-After": "0"}),
               httpx.Response(status, json=payload)]
    recorder = Recorder(lambda request: replies.pop(0))
    endpoint = run(make(mode, recorder).webhooks.create(name="h", url="https://example.com/h", subscribed_events=["job.failed"]))
    assert isinstance(endpoint, WebhookEndpointWithSecret) and len(recorder.sent) == 2


@pytest.mark.parametrize("mode", MODES)
def test_a_long_retry_after_on_a_write_raises_with_it(mode: str) -> None:
    respond = lambda request: httpx.Response(429, json={"error": {"code": "RATE_LIMITED", "message": "slow"}},  # noqa: E731
                                            headers={"Retry-After": "3600"})
    with pytest.raises(RateLimitError) as info:
        run(make(mode, Recorder(respond)).notifications.mark_read(["ntf_1"]))
    assert info.value.retry_after == 3600


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("call", [
    lambda rb: rb.webhooks.get("../x"), lambda rb: rb.assets.delete(""), lambda rb: rb.storage.get("a/b"),
    lambda rb: rb.api_keys.revoke(".."), lambda rb: rb.orgs.members.remove("m/1"), lambda rb: rb.jobs.logs("job 1"),
    lambda rb: rb.billing.delete_payment_method("pm?x"), lambda rb: rb.storage.list_supabase_buckets("st", "a/b"),
])
def test_an_id_that_is_not_one_path_segment_is_refused_before_any_request(mode: str, call: Callable[[Any], Any]) -> None:
    recorder = Recorder(json_response(200, {}))
    with pytest.raises(InvalidArgumentError):
        run(call(make(mode, recorder)))
    assert recorder.sent == []


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("call", [
    lambda rb: rb.assets.list(limit=0), lambda rb: rb.assets.list(offset=-1), lambda rb: rb.billing.transactions(page=0),
    lambda rb: rb.webhooks.list_deliveries(limit="5"), lambda rb: rb.billing.usage_by_client(days=0),
    lambda rb: rb.billing.checkout_credits(0), lambda rb: rb.billing.checkout_credits(True),
    lambda rb: rb.webhooks.create(name="h", url="https://x", subscribed_events="job.completed"),
    lambda rb: rb.notifications.mark_read("ntf_1"), lambda rb: rb.webhooks.update("whe_1", active="yes"),
    lambda rb: rb.api_keys.create(expires_in=-5), lambda rb: rb.compose.validate(["not", "a", "dict"]),
    lambda rb: rb.storage.create({"id": "media"}), lambda rb: rb.storage.update("media", credentials="AKIA"),
    lambda rb: rb.jobs.list(client=5), lambda rb: rb.jobs.list(from_=-1),
])
def test_a_bad_argument_is_refused_before_any_request(mode: str, call: Callable[[Any], Any]) -> None:
    recorder = Recorder(json_response(200, {}))
    with pytest.raises(InvalidArgumentError):
        run(call(make(mode, recorder)))
    assert recorder.sent == []


@pytest.mark.parametrize("mode", MODES)
def test_a_method_without_a_key_raises_before_sending(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDOBAR_API_KEY", raising=False)
    recorder = Recorder(json_response(200, {}))
    client = (Rendobar if mode == "sync" else AsyncRendobar)(base_url="https://api.test")
    _install(client._core._client_wrapper.httpx_client.httpx_client, recorder)  # noqa: SLF001
    with pytest.raises(AuthenticationError) as info:
        run(client.billing.state())
    assert info.value.code == "MISSING_API_KEY" and recorder.sent == []


def test_a_closed_client_refuses_resource_calls() -> None:
    rb = Rendobar("rb_k", base_url="https://api.test")
    rb.close()
    with pytest.raises(RendobarError) as info:
        rb.webhooks.list()
    assert info.value.code == "CLIENT_CLOSED"


def test_jobs_list_sends_the_new_filters() -> None:
    page = {"data": [], "meta": {"total": 0, "page": 1, "limit": 10}}
    recorder = Recorder(json_response(200, page))
    rb = make("sync", recorder)
    assert isinstance(rb, Rendobar)
    rb.jobs.list(sort="cost", order="asc", client="python", from_=1, to=2, limit=10)
    assert recorder.sent[0].query == {"sort": "cost", "order": "asc", "client": "python", "from": "1", "to": "2", "limit": "10"}


# ── uploads ───────────────────────────────────────────────────────────

ASSET = answer("getAsset")[1]["data"]


class Storage:
    """The API and the presigned storage URLs, both answered here. Records every request in order."""

    def __init__(self, init: Dict[str, Any], *, etag: Optional[str] = '"etag"', put_failures: int = 0) -> None:
        self.init = init
        self.etag = etag
        self.put_failures = put_failures
        self.puts: Dict[str, bytes] = {}
        self.requests: List[Tuple[str, str]] = []
        self.completed: Any = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, f"{request.url.host}{request.url.path}"))
        if request.url.host == "storage.test":
            if self.put_failures:
                self.put_failures -= 1
                return httpx.Response(503)
            self.puts[request.url.path] = request.read()
            assert request.headers.get("authorization") is None, "the API key must never reach storage"
            return httpx.Response(200, headers={"etag": f'{self.etag}-{request.url.path}'} if self.etag else {})
        if request.url.path == "/assets" and request.method == "POST":
            return httpx.Response(201, json=self.init)
        if request.url.path.endswith("/complete"):
            content = request.read()
            self.completed = json.loads(content) if content else None
            return httpx.Response(200, json={"data": dict(ASSET, status="ready")})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": request.url.path}})


def presigned() -> Dict[str, Any]:
    return {"status": "presigned", "data": dict(ASSET, id="asset_1"), "upload": {"method": "PUT", "url": "https://storage.test/one", "expiresAt": 1}}


def multipart(size: int, part_size: int) -> Dict[str, Any]:
    count = -(-size // part_size)
    parts = [{"partNumber": n, "url": f"https://storage.test/part{n}"} for n in range(count, 0, -1)]  # out of order on purpose
    return {"status": "multipart", "data": dict(ASSET, id="asset_1"),
            "upload": {"uploadId": "u1", "partSize": part_size, "parts": parts, "expiresAt": 1}}


@pytest.mark.parametrize("mode", MODES)
def test_a_small_upload_is_one_put_then_complete(mode: str, tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x" * 3000)
    storage = Storage(presigned())
    seen: List[UploadProgress] = []
    asset = run(make(mode, storage).uploads.create(clip, content_type="video/mp4", on_progress=seen.append))
    assert isinstance(asset, Asset) and asset.status == "ready"
    assert storage.requests == [("POST", "api.test/assets"), ("PUT", "storage.test/one"), ("POST", "api.test/assets/asset_1/complete")]
    assert storage.puts["/one"] == b"x" * 3000
    assert storage.completed == {}
    assert seen == [UploadProgress(3000, 3000)]


def test_the_upload_init_names_the_file_and_its_lifecycle() -> None:
    sent: List[Any] = []
    storage = Storage(presigned())

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/assets":
            sent.append(json.loads(request.read()))
        return storage(request)

    make("sync", handle).uploads.create(b"abc", filename="a.srt", persist=True)
    assert sent == [{"filename": "a.srt", "size": 3, "lifecycle": "persisted"}]


@pytest.mark.parametrize("mode", MODES)
def test_a_large_upload_sends_every_part_and_completes_with_the_etags_in_order(mode: str) -> None:
    data = bytes(range(256)) * 40  # 10240 bytes in parts of 4096, 4096, 2048
    storage = Storage(multipart(len(data), 4096))
    seen: List[UploadProgress] = []
    asset = run(make(mode, storage).uploads.create(data, filename="big.bin", concurrency=2, on_progress=seen.append))
    assert isinstance(asset, Asset)
    assert b"".join(storage.puts[f"/part{n}"] for n in (1, 2, 3)) == data
    assert storage.completed == {"parts": [{"partNumber": n, "etag": f'"etag"-/part{n}'} for n in (1, 2, 3)]}
    assert seen[-1] == UploadProgress(len(data), len(data)) and len(seen) == 3


@pytest.mark.parametrize("mode", MODES)
def test_a_multipart_part_without_an_etag_fails_the_upload(mode: str) -> None:
    storage = Storage(multipart(10, 4), etag=None)
    with pytest.raises(RendobarError) as info:
        run(make(mode, storage).uploads.create(b"0123456789", filename="a.bin"))
    assert info.value.code == "UPLOAD_FAILED" and storage.completed is None


@pytest.mark.parametrize("mode", MODES)
def test_a_put_that_fails_is_retried(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendobar._resources, "upload_pause", lambda attempt: 0.0)  # noqa: SLF001
    monkeypatch.setattr(rendobar._async_resources, "upload_pause", lambda attempt: 0.0)  # noqa: SLF001
    storage = Storage(presigned(), put_failures=2)
    run(make(mode, storage).uploads.create(b"abc", filename="a.bin"))
    assert [r for r in storage.requests if r[0] == "PUT"] == [("PUT", "storage.test/one")] * 3


@pytest.mark.parametrize("mode", MODES)
def test_a_put_that_keeps_failing_raises_upload_failed(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendobar._resources, "upload_pause", lambda attempt: 0.0)  # noqa: SLF001
    monkeypatch.setattr(rendobar._async_resources, "upload_pause", lambda attempt: 0.0)  # noqa: SLF001
    storage = Storage(presigned(), put_failures=10)
    with pytest.raises(RendobarError) as info:
        run(make(mode, storage).uploads.create(b"abc", filename="a.bin"))
    assert info.value.code == "UPLOAD_FAILED" and info.value.status_code == 503 and storage.completed is None


@pytest.mark.parametrize("mode", MODES)
def test_a_deduplicated_upload_sends_no_bytes(mode: str) -> None:
    storage = Storage({"status": "deduplicated", "data": dict(ASSET, id="asset_9", status="ready")})
    asset = run(make(mode, storage).uploads.create(b"abc", filename="a.bin", checksum="ab" * 32))
    assert asset.id == "asset_9" and storage.requests == [("POST", "api.test/assets")]


@pytest.mark.parametrize("mode", MODES)
def test_an_upload_init_this_sdk_cannot_read_raises(mode: str) -> None:
    storage = Storage({"status": "teleported", "data": ASSET})
    with pytest.raises(ResponseValidationError):
        run(make(mode, storage).uploads.create(b"abc", filename="a.bin"))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("args, kwargs", [
    ((b"abc",), {}), (("/no/such/file.mp4",), {}), ((12,), {}), ((b"abc",), {"filename": ""}),
    ((b"abc",), {"filename": "a", "concurrency": 0}), ((b"abc",), {"filename": "a", "persist": "yes"}),
])
def test_a_bad_upload_argument_is_refused_before_any_request(mode: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
    recorder = Recorder(json_response(200, {}))
    with pytest.raises(InvalidArgumentError):
        run(make(mode, recorder).uploads.create(*args, **kwargs))
    assert recorder.sent == []

"""The asyncio client's resources beyond jobs: the same methods as `_resources`, awaited.

Argument checks, request bodies, readers and the upload plan are shared with
the sync resources. This file only awaits, sleeps and reads files off the
event loop.
"""
# pyright: strict, reportPrivateUsage=false
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator, Callable, Dict, List, Mapping, Optional, Sequence

import httpx

from ._errors import RendobarError, to_public
from ._models import PageMeta
from ._plumbing import Page, empty, listed, one, page_window, paged, path_segment, text, texts, whole
from ._resource_models import (
    AccountBuckets,
    ApiKey,
    ApiKeyRevoked,
    Asset,
    AssetDeleted,
    AssetDownload,
    AssetKind,
    AssetLifecycle,
    AssetScope,
    AssetStatus,
    AwsAccess,
    BillingPortal,
    BillingState,
    BucketProvider,
    ClientUsage,
    ComposeEffects,
    ComposeEngineEffects,
    ComposeValidation,
    CreatedApiKey,
    CreditsCheckout,
    CreditsInterval,
    CurrentOrg,
    DefaultPaymentMethod,
    DeliveriesPageMeta,
    Invitation,
    InvitationRevoked,
    InviteRole,
    Invoice,
    ListMeta,
    MemberRemoved,
    MemberRole,
    MemberRoleChanged,
    NewOrganization,
    Notification,
    NotificationsMeta,
    NotificationsRead,
    OffsetPageMeta,
    Organization,
    OrgMembership,
    OrgSettings,
    PaidPlan,
    PaymentMethod,
    PlanCheckout,
    PreparedAwsStorage,
    Region,
    RetriedDelivery,
    S3BucketLookup,
    StorageActivity,
    StorageConflict,
    StorageConnection,
    StorageCreate,
    StorageCredentials,
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
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEndpointWithSecret,
    WebhookEventType,
    WebhookTestResult,
)
from ._resources import (
    UPLOAD_ATTEMPTS,
    Part,
    Source,
    UploadSource,
    body,
    completed_parts,
    compose_params,
    credit_amount,
    flag,
    init_fields,
    missing_etag,
    read_compose_validation,
    read_plan_checkout,
    storage_create,
    storage_credentials,
    upload_failed,
    upload_options,
    upload_pause,
    upload_plan,
    usage_days,
)

if TYPE_CHECKING:
    from ._async_client import AsyncRendobar


class AsyncBilling:
    """Same methods as `Rendobar.billing`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.billing.with_raw_response

    async def state(self) -> BillingState:
        return await self._client._read("GET", "/billing/state", self._raw.get_billing_state, one(BillingState))

    async def usage(self, *, start: Optional[str] = None, end: Optional[str] = None) -> UsageSummary:
        text("start", start)
        text("end", end)
        return await self._client._read("GET", "/billing/usage", lambda: self._raw.get_usage(start=start, end=end), one(UsageSummary))

    async def usage_by_client(self, *, days: Optional[int] = None) -> List[ClientUsage]:
        lookback = usage_days(days)
        return await self._client._read("GET", "/billing/usage-by-client", lambda: self._raw.get_usage_by_client(days=lookback),
                                        listed(ClientUsage))

    async def transactions(self, *, page: Optional[int] = None, limit: Optional[int] = None) -> Page[Transaction, PageMeta]:
        whole("page", page, 1)
        page_window(limit, None)
        return await self._client._read("GET", "/billing/transactions", lambda: self._raw.list_transactions(page=page, limit=limit),
                                        paged(Transaction, PageMeta))

    async def history(self, *, page: Optional[int] = None, limit: Optional[int] = None) -> Page[Invoice, PageMeta]:
        whole("page", page, 1)
        page_window(limit, None)
        return await self._client._read("GET", "/billing/history", lambda: self._raw.list_invoices(page=page, limit=limit),
                                        paged(Invoice, PageMeta))

    async def checkout_credits(self, amount: float, *, interval: Optional[CreditsInterval] = None) -> CreditsCheckout:
        credit_amount(amount)
        return await self._client._read("POST", "/billing/checkout/credits", lambda: self._raw.create_credits_checkout(
            amount=amount, request_options=body({"interval": interval})), one(CreditsCheckout))

    async def checkout_plan(self, plan: PaidPlan) -> PlanCheckout:
        text("plan", plan)
        return await self._client._read("POST", "/billing/checkout/plan", lambda: self._raw.create_plan_checkout(plan=plan),
                                        read_plan_checkout)

    async def cancel_subscription(self) -> Subscription:
        return await self._client._read("PATCH", "/billing/subscription",
                                        lambda: self._raw.update_subscription(cancel_at_period_end=True), one(Subscription))

    async def reactivate_subscription(self) -> Subscription:
        return await self._client._read("PATCH", "/billing/subscription",
                                        lambda: self._raw.update_subscription(cancel_at_period_end=False), one(Subscription))

    async def cancel_credit_schedule(self) -> None:
        await self._client._read("DELETE", "/billing/credit-schedule", self._raw.cancel_credit_schedule, empty)

    async def payment_methods(self) -> List[PaymentMethod]:
        return await self._client._read("GET", "/billing/payment-methods", self._raw.list_payment_methods, listed(PaymentMethod))

    async def delete_payment_method(self, payment_method_id: str) -> None:
        safe = path_segment("payment_method_id", payment_method_id)
        await self._client._read("DELETE", f"/billing/payment-methods/{safe}", lambda: self._raw.delete_payment_method(safe), empty)

    async def set_default_payment_method(self, payment_method_id: str) -> DefaultPaymentMethod:
        safe = path_segment("payment_method_id", payment_method_id)
        return await self._client._read("PATCH", f"/billing/payment-methods/{safe}/default",
                                        lambda: self._raw.set_default_payment_method(safe), one(DefaultPaymentMethod))

    async def portal_url(self) -> BillingPortal:
        return await self._client._read("GET", "/billing/payment-methods/portal-url", self._raw.get_billing_portal_url,
                                        one(BillingPortal))


async def _stream(source: Source, part: Part) -> AsyncIterator[bytes]:
    """The part's bytes, read in a worker thread so a slow disk never blocks the event loop."""
    chunks = source.chunks(part.offset, part.length)
    try:
        while True:
            block = await asyncio.to_thread(next, chunks, None)
            if block is None:
                return
            yield block
    finally:
        chunks.close()


class AsyncUploads:
    """Same methods as `Rendobar.uploads`, awaited. Parts of a large file upload concurrently on the event loop."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.assets.with_raw_response

    async def create(
        self,
        file: UploadSource,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        checksum: Optional[str] = None,
        persist: bool = False,
        concurrency: int = 5,
        on_progress: Optional[Callable[[UploadProgress], None]] = None,
    ) -> Asset:
        """Upload `file` and return the ready asset. Same arguments as `Rendobar.uploads.create`."""
        source = Source(file, filename)
        upload_options(concurrency, on_progress)
        fields = init_fields(source, content_type, checksum, persist)
        plan = await self._client._read("POST", "/assets", lambda: self._raw.create_asset(
            filename=source.filename, size=source.size, request_options=body(fields)), lambda response: upload_plan(response, source.size))
        loaded = 0

        def report(size: int) -> None:
            nonlocal loaded
            loaded = min(source.size, loaded + size)
            if on_progress is not None:
                on_progress(UploadProgress(loaded, source.size))

        if plan.status == "deduplicated":
            report(source.size)
            return plan.asset
        safe = path_segment("asset id", plan.asset.id)
        if plan.status == "presigned":
            await self._put(source, plan.parts[0])
            report(source.size)
            return await self._client._read("POST", f"/assets/{safe}/complete", lambda: self._raw.complete_asset_upload(safe), one(Asset))
        etags = await self._parts(source, plan.parts, concurrency, report)
        return await self._client._read("POST", f"/assets/{safe}/complete", lambda: self._raw.complete_asset_upload(
            safe, request_options=body({"parts": completed_parts(etags)})), one(Asset))

    async def _parts(self, source: Source, parts: Sequence[Part], concurrency: int, report: Callable[[int], None]) -> Dict[int, str]:
        etags: Dict[int, str] = {}
        gate = asyncio.Semaphore(concurrency)

        async def send(part: Part) -> None:
            async with gate:
                etag = await self._put(source, part)
            if etag is None:
                raise missing_etag()
            etags[part.number] = etag
            report(part.length)

        tasks = [asyncio.ensure_future(send(part)) for part in parts]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()  # the first failure stops the parts still waiting or in flight
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return etags

    async def _put(self, source: Source, part: Part) -> Optional[str]:
        last: Optional[RendobarError] = None
        for attempt in range(UPLOAD_ATTEMPTS):
            if attempt:
                await asyncio.sleep(upload_pause(attempt - 1))
            try:
                response = await self._client._http.put(part.url, content=_stream(source, part),
                                                        headers={"Content-Length": str(part.length)})
            except httpx.TransportError as err:
                last = to_public(err)
                continue
            if response.is_success:
                etag: Optional[str] = response.headers.get("etag")
                return etag
            last = upload_failed(response.status_code)
        assert last is not None
        raise last


class AsyncAssets:
    """Same methods as `Rendobar.assets`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.assets.with_raw_response

    async def list(
        self,
        *,
        kind: Optional[AssetKind] = None,
        scope: Optional[AssetScope] = None,
        status: Optional[AssetStatus] = None,
        lifecycle: Optional[AssetLifecycle] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Page[Asset, OffsetPageMeta]:
        page_window(limit, offset)
        return await self._client._read("GET", "/assets", lambda: self._raw.list_assets(
            kind=kind, scope=scope, status=status, lifecycle=lifecycle, limit=limit, offset=offset), paged(Asset, OffsetPageMeta))

    async def get(self, asset_id: str) -> Asset:
        safe = path_segment("asset_id", asset_id)
        return await self._client._read("GET", f"/assets/{safe}", lambda: self._raw.get_asset(safe), one(Asset))

    async def delete(self, asset_id: str) -> AssetDeleted:
        safe = path_segment("asset_id", asset_id)
        return await self._client._read("DELETE", f"/assets/{safe}", lambda: self._raw.delete_asset(safe), one(AssetDeleted))

    async def download(self, asset_id: str) -> AssetDownload:
        safe = path_segment("asset_id", asset_id)
        return await self._client._read("GET", f"/assets/{safe}/download", lambda: self._raw.download_asset(safe), one(AssetDownload))

    async def templates(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> Page[Asset, OffsetPageMeta]:
        page_window(limit, offset)
        return await self._client._read("GET", "/assets/templates", lambda: self._raw.list_asset_templates(limit=limit, offset=offset),
                                        paged(Asset, OffsetPageMeta))


class AsyncWebhooks:
    """Same methods as `Rendobar.webhooks`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.webhooks.with_raw_response

    async def create(self, *, name: str, url: str, subscribed_events: List[WebhookEventType]) -> WebhookEndpointWithSecret:
        text("name", name)
        text("url", url)
        texts("subscribed_events", subscribed_events)
        return await self._client._read("POST", "/webhooks/endpoints", lambda: self._raw.create_webhook_endpoint(
            name=name, url=url, subscribed_events=subscribed_events), one(WebhookEndpointWithSecret))

    async def list(self) -> Page[WebhookEndpoint, ListMeta]:
        return await self._client._read("GET", "/webhooks/endpoints", self._raw.list_webhook_endpoints, paged(WebhookEndpoint, ListMeta))

    async def get(self, endpoint_id: str) -> WebhookEndpoint:
        safe = path_segment("endpoint_id", endpoint_id)
        return await self._client._read("GET", f"/webhooks/endpoints/{safe}", lambda: self._raw.get_webhook_endpoint(safe),
                                        one(WebhookEndpoint))

    async def update(
        self,
        endpoint_id: str,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        subscribed_events: Optional[List[WebhookEventType]] = None,
        active: Optional[bool] = None,
    ) -> WebhookEndpoint:
        safe = path_segment("endpoint_id", endpoint_id)
        text("name", name)
        text("url", url)
        flag("active", active)
        events = None if subscribed_events is None else texts("subscribed_events", subscribed_events)
        fields = {"name": name, "url": url, "subscribedEvents": events, "active": active}
        return await self._client._read("PATCH", f"/webhooks/endpoints/{safe}",
                                        lambda: self._raw.update_webhook_endpoint(safe, request_options=body(fields)), one(WebhookEndpoint))

    async def delete(self, endpoint_id: str) -> None:
        safe = path_segment("endpoint_id", endpoint_id)
        await self._client._read("DELETE", f"/webhooks/endpoints/{safe}", lambda: self._raw.delete_webhook_endpoint(safe), empty)

    async def rotate_secret(self, endpoint_id: str) -> WebhookEndpointWithSecret:
        safe = path_segment("endpoint_id", endpoint_id)
        return await self._client._read("POST", f"/webhooks/endpoints/{safe}/secret", lambda: self._raw.rotate_webhook_secret(safe),
                                        one(WebhookEndpointWithSecret))

    async def test(self, endpoint_id: str) -> WebhookTestResult:
        safe = path_segment("endpoint_id", endpoint_id)
        return await self._client._read("POST", f"/webhooks/endpoints/{safe}/test", lambda: self._raw.test_webhook_endpoint(safe),
                                        one(WebhookTestResult))

    async def list_deliveries(
        self,
        *,
        endpoint_id: Optional[str] = None,
        event: Optional[str] = None,
        status: Optional[WebhookDeliveryStatus] = None,
        job_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Page[WebhookDelivery, DeliveriesPageMeta]:
        page_window(limit, offset)
        for name, value in (("endpoint_id", endpoint_id), ("event", event), ("job_id", job_id)):
            text(name, value)
        return await self._client._read("GET", "/webhooks/deliveries", lambda: self._raw.list_webhook_deliveries(
            endpoint_id=endpoint_id, event=event, status=status, job_id=job_id, limit=limit, offset=offset),
            paged(WebhookDelivery, DeliveriesPageMeta))

    async def retry_delivery(self, delivery_id: str) -> RetriedDelivery:
        safe = path_segment("delivery_id", delivery_id)
        return await self._client._read("POST", f"/webhooks/deliveries/{safe}/retry", lambda: self._raw.retry_webhook_delivery(safe),
                                        one(RetriedDelivery))


class AsyncStorage:
    """Same methods as `Rendobar.storage`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.storage.with_raw_response

    async def create(self, params: StorageCreate) -> StorageConnection:
        request = storage_create(params)
        return await self._client._read("POST", "/storage", lambda: self._raw.create_storage(request=request), one(StorageConnection))

    async def list(self) -> Page[StorageConnection, ListMeta]:
        return await self._client._read("GET", "/storage", self._raw.list_storage, paged(StorageConnection, ListMeta))

    async def get(self, storage_id: str) -> StorageConnection:
        safe = path_segment("storage_id", storage_id)
        return await self._client._read("GET", f"/storage/{safe}", lambda: self._raw.get_storage(safe), one(StorageConnection))

    async def update(
        self,
        storage_id: str,
        *,
        credentials: Optional[StorageCredentials] = None,
        public_base_url: Optional[str] = None,
        path_template: Optional[str] = None,
        on_conflict: Optional[StorageConflict] = None,
        default_destination: Optional[bool] = None,
    ) -> StorageConnection:
        safe = path_segment("storage_id", storage_id)
        text("public_base_url", public_base_url)
        text("path_template", path_template)
        flag("default_destination", default_destination)
        fields = {"credentials": storage_credentials(credentials), "publicBaseUrl": public_base_url, "pathTemplate": path_template,
                  "onConflict": on_conflict, "defaultDestination": default_destination}
        return await self._client._read("PATCH", f"/storage/{safe}", lambda: self._raw.update_storage(safe, request_options=body(fields)),
                                        one(StorageConnection))

    async def delete(self, storage_id: str) -> None:
        safe = path_segment("storage_id", storage_id)
        await self._client._read("DELETE", f"/storage/{safe}", lambda: self._raw.delete_storage(safe), empty)

    async def test(self, storage_id: str) -> StorageTestResult:
        safe = path_segment("storage_id", storage_id)
        return await self._client._read("POST", f"/storage/{safe}/test", lambda: self._raw.test_storage(safe), one(StorageTestResult))

    async def stats(self, storage_id: str) -> StorageActivity:
        safe = path_segment("storage_id", storage_id)
        return await self._client._read("GET", f"/storage/{safe}/stats", lambda: self._raw.get_storage_stats(safe), one(StorageActivity))

    async def list_objects(self, storage_id: str, *, prefix: Optional[str] = None, cursor: Optional[str] = None,
                           limit: Optional[int] = None) -> StorageObjects:
        safe = path_segment("storage_id", storage_id)
        text("prefix", prefix)
        text("cursor", cursor)
        page_window(limit, None)
        return await self._client._read("GET", f"/storage/{safe}/objects", lambda: self._raw.list_storage_objects(
            safe, prefix=prefix or None, cursor=cursor or None, limit=limit), one(StorageObjects))

    async def prepare_aws(
        self,
        *,
        id: str,
        bucket: str,
        region: Optional[str] = None,
        public_base_url: Optional[str] = None,
        create_bucket: Optional[bool] = None,
        access: Optional[AwsAccess] = None,
    ) -> PreparedAwsStorage:
        for name, value in (("id", id), ("bucket", bucket), ("region", region), ("public_base_url", public_base_url)):
            text(name, value)
        flag("create_bucket", create_bucket)
        fields = {"region": region, "publicBaseUrl": public_base_url, "createBucket": create_bucket, "access": access}
        return await self._client._read("POST", "/storage/aws/prepare", lambda: self._raw.prepare_aws_storage(
            id=id, bucket=bucket, request_options=body(fields)), one(PreparedAwsStorage))

    async def list_account_buckets(self, *, provider: BucketProvider = "s3") -> AccountBuckets:
        return await self._client._read("GET", "/storage/buckets", lambda: self._raw.list_account_buckets(provider=provider),
                                        one(AccountBuckets))

    async def look_up_s3_bucket(self, name: str) -> S3BucketLookup:
        text("name", name)
        return await self._client._read("GET", "/storage/s3/bucket", lambda: self._raw.look_up_s3bucket(name=name), one(S3BucketLookup))

    async def start_supabase(self) -> SupabaseSignIn:
        return await self._client._read("POST", "/storage/supabase/start", self._raw.start_supabase_storage, one(SupabaseSignIn))

    async def list_supabase_projects(self, state: str) -> SupabaseProjects:
        safe = path_segment("state", state)
        return await self._client._read("GET", f"/storage/supabase/sessions/{safe}", lambda: self._raw.get_supabase_session(safe),
                                        one(SupabaseProjects))

    async def list_supabase_buckets(self, state: str, project_ref: str) -> SupabaseBuckets:
        session = path_segment("state", state)
        project = path_segment("project_ref", project_ref)
        return await self._client._read("GET", f"/storage/supabase/sessions/{session}/projects/{project}/buckets",
                                        lambda: self._raw.list_supabase_buckets(session, project), one(SupabaseBuckets))

    async def finish_supabase(
        self,
        *,
        state: str,
        project_ref: str,
        id: str,
        bucket: str,
        public_base_url: Optional[str] = None,
        create_bucket: Optional[bool] = None,
    ) -> StorageConnection:
        for name, value in (("state", state), ("project_ref", project_ref), ("id", id), ("bucket", bucket),
                            ("public_base_url", public_base_url)):
            text(name, value)
        flag("create_bucket", create_bucket)
        fields = {"publicBaseUrl": public_base_url, "createBucket": create_bucket}
        return await self._client._read("POST", "/storage/supabase/finish", lambda: self._raw.finish_supabase_storage(
            state=state, project_ref=project_ref, id=id, bucket=bucket, request_options=body(fields)), one(StorageConnection))


class AsyncApiKeys:
    """Same methods as `Rendobar.api_keys`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.api_keys.with_raw_response

    async def create(self, *, name: Optional[str] = None, expires_in: Optional[int] = None,
                     scopes: Optional[List[str]] = None) -> CreatedApiKey:
        text("name", name)
        whole("expires_in", expires_in, 1)
        granted = None if scopes is None else texts("scopes", scopes)
        return await self._client._read("POST", "/api-keys", lambda: self._raw.create_api_key(
            request_options=body({"name": name, "expiresIn": expires_in, "scopes": granted})), one(CreatedApiKey))

    async def list(self) -> List[ApiKey]:
        return await self._client._read("GET", "/api-keys", self._raw.list_api_keys, listed(ApiKey))

    async def revoke(self, key_id: str) -> ApiKeyRevoked:
        safe = path_segment("key_id", key_id)
        return await self._client._read("DELETE", f"/api-keys/{safe}", lambda: self._raw.revoke_api_key(safe), one(ApiKeyRevoked))

    async def update(self, key_id: str, *, name: Optional[str] = None, enabled: Optional[bool] = None) -> ApiKey:
        safe = path_segment("key_id", key_id)
        text("name", name)
        flag("enabled", enabled)
        return await self._client._read("PATCH", f"/api-keys/{safe}", lambda: self._raw.update_api_key(
            safe, request_options=body({"name": name, "enabled": enabled})), one(ApiKey))


class AsyncMembers:
    """Same methods as `Rendobar.orgs.members`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response

    async def invite(self, *, email: str, role: InviteRole) -> Invitation:
        text("email", email)
        return await self._client._read("POST", "/orgs/current/members", lambda: self._raw.invite_org_member(email=email, role=role),
                                        one(Invitation))

    async def change_role(self, member_id: str, *, role: MemberRole) -> MemberRoleChanged:
        safe = path_segment("member_id", member_id)
        return await self._client._read("PATCH", f"/orgs/current/members/{safe}",
                                        lambda: self._raw.update_org_member_role(safe, role=role), one(MemberRoleChanged))

    async def remove(self, member_id: str) -> MemberRemoved:
        safe = path_segment("member_id", member_id)
        return await self._client._read("DELETE", f"/orgs/current/members/{safe}", lambda: self._raw.remove_org_member(safe),
                                        one(MemberRemoved))


class AsyncInvitations:
    """Same methods as `Rendobar.orgs.invitations`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response

    async def revoke(self, invitation_id: str) -> InvitationRevoked:
        safe = path_segment("invitation_id", invitation_id)
        return await self._client._read("DELETE", f"/orgs/current/invitations/{safe}", lambda: self._raw.revoke_org_invitation(safe),
                                        one(InvitationRevoked))


class AsyncOrgs:
    """Same methods as `Rendobar.orgs`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response
        self.members = AsyncMembers(client)
        self.invitations = AsyncInvitations(client)

    async def list(self) -> List[OrgMembership]:
        return await self._client._read("GET", "/orgs", self._raw.list_orgs, listed(OrgMembership))

    async def current(self) -> CurrentOrg:
        return await self._client._read("GET", "/orgs/current", self._raw.get_current_org, one(CurrentOrg))

    async def create(self, *, name: str, slug: str) -> NewOrganization:
        text("name", name)
        text("slug", slug)
        return await self._client._read("POST", "/orgs", lambda: self._raw.create_org(name=name, slug=slug), one(NewOrganization))

    async def update(self, *, name: Optional[str] = None, slug: Optional[str] = None) -> Organization:
        text("name", name)
        text("slug", slug)
        return await self._client._read("PATCH", "/orgs/current",
                                        lambda: self._raw.update_org(request_options=body({"name": name, "slug": slug})), one(Organization))

    async def delete(self) -> None:
        await self._client._read("DELETE", "/orgs/current", self._raw.delete_org, empty)

    async def get_settings(self) -> OrgSettings:
        return await self._client._read("GET", "/orgs/current/settings", self._raw.get_org_settings, one(OrgSettings))

    async def update_settings(
        self,
        *,
        billing_emails_enabled: Optional[bool] = None,
        default_region: Optional[Region] = None,
        region_pinned: Optional[bool] = None,
        product_analytics_enabled: Optional[bool] = None,
    ) -> OrgSettings:
        for name, value in (("billing_emails_enabled", billing_emails_enabled), ("region_pinned", region_pinned),
                            ("product_analytics_enabled", product_analytics_enabled)):
            flag(name, value)
        fields: Mapping[str, object] = {
            "billingEmailsEnabled": billing_emails_enabled, "defaultRegion": default_region, "regionPinned": region_pinned,
            "productAnalyticsEnabled": product_analytics_enabled}
        return await self._client._read("PATCH", "/orgs/current/settings",
                                        lambda: self._raw.update_org_settings(request_options=body(fields)), one(OrgSettings))


class AsyncCompose:
    """Same methods as `Rendobar.compose`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.compose.with_raw_response

    async def effects(self) -> ComposeEffects:
        return await self._client._read("GET", "/compose/effects", self._raw.list_compose_effects, one(ComposeEffects))

    async def engine_effects(self) -> ComposeEngineEffects:
        return await self._client._read("GET", "/compose/effects/engine", self._raw.list_compose_engine_effects,
                                        one(ComposeEngineEffects))

    async def validate(self, params: Mapping[str, object]) -> ComposeValidation:
        document = compose_params(params)
        return await self._client._read("POST", "/compose/validate", lambda: self._raw.validate_compose(params=document),
                                        read_compose_validation, replayable=True)


class AsyncNotifications:
    """Same methods as `Rendobar.notifications`, awaited."""

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client
        self._raw = client._core.notifications.with_raw_response

    async def list(self) -> Page[Notification, NotificationsMeta]:
        return await self._client._read("GET", "/notifications", self._raw.list_notifications, paged(Notification, NotificationsMeta))

    async def mark_read(self, ids: List[str]) -> NotificationsRead:
        chosen = texts("ids", ids)
        return await self._client._read("POST", "/notifications/read", lambda: self._raw.mark_notifications_read(ids=chosen),
                                        one(NotificationsRead), replayable=True)

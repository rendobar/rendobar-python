"""The sync client's resources beyond jobs: billing, uploads, assets, webhooks, storage,
API keys, organizations, compose and notifications. Same names as `@rendobar/sdk`.

Each method checks its arguments, makes one generated core call through
`Rendobar._read` (retries, errors, deprecation notices) and reads the answer
into its public model (`_plumbing` readers). What is not I/O (argument checks,
request bodies, the upload plan) lives here as plain functions that
`_async_resources` reuses, so the two clients behave the same.

Writes that are not keyed (creating an endpoint, a key, a checkout) are not
retried after a 5xx: the first attempt may have taken effect.
"""
# pyright: strict, reportPrivateUsage=false
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import FIRST_EXCEPTION, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Generator, List, Literal, Mapping, Optional, Sequence, Union

import httpx
import pydantic

from ._errors import InvalidArgumentError, RendobarError, as_list, as_mapping, is_text, to_public
from ._generated.core.request_options import RequestOptions
from ._generated.core.serialization import convert_and_respect_annotation_metadata
from ._models import PageMeta
from ._plumbing import Page, empty, listed, one, page_window, paged, path_segment, text, texts, union, unread, whole
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

if TYPE_CHECKING:
    from ._client import Rendobar

# ── request bodies ─────────────────────────────────────────────────────


def body(fields: Mapping[str, object]) -> RequestOptions:
    """The fields that are set, sent as the JSON body in the API's names. An unset field is left out, never sent as null."""
    return RequestOptions(additional_body_parameters={key: value for key, value in fields.items() if value is not None})


def flag(name: str, value: Optional[bool]) -> None:
    if value is not None and value is not True and value is not False:
        raise InvalidArgumentError(f"{name} must be True or False. Got {value!r}.")


def storage_credentials(credentials: Optional[StorageCredentials]) -> object:
    """`credentials` of storage.update() in the API's field names (`access_key_id` becomes `accessKeyId`)."""
    if credentials is None:
        return None
    if as_mapping(credentials) is None:
        raise InvalidArgumentError('credentials must be a dict, such as {"type": "keys", "access_key_id": ..., "secret_access_key": ...}.')
    converted: object = convert_and_respect_annotation_metadata(object_=credentials, annotation=StorageCredentials, direction="write")
    return converted


def storage_create(params: StorageCreate) -> StorageCreate:
    """storage.create()'s dict, checked for the one field every provider needs before it is sent."""
    fields = as_mapping(params)
    if fields is None or not isinstance(fields.get("provider"), str):
        raise InvalidArgumentError('params must be a dict with a "provider", such as {"provider": "s3", "id": "prod-media", ...}.')
    return params


def credit_amount(amount: object) -> None:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise InvalidArgumentError(f"amount must be a positive number of US dollars. Got {amount!r}.")


def usage_days(days: Optional[int]) -> Optional[str]:
    whole("days", days, 1)
    return None if days is None else str(days)


_PLAN_CHECKOUT_ADAPTER: "pydantic.TypeAdapter[PlanCheckout]" = pydantic.TypeAdapter(PlanCheckout)
_COMPOSE_ADAPTER: "pydantic.TypeAdapter[ComposeValidation]" = pydantic.TypeAdapter(ComposeValidation)
read_plan_checkout = union(_PLAN_CHECKOUT_ADAPTER)
read_compose_validation = union(_COMPOSE_ADAPTER)


def compose_params(params: Mapping[str, object]) -> Dict[str, object]:
    fields = as_mapping(params)
    if fields is None:
        raise InvalidArgumentError(f"params must be a dict of compose params. Got {type(params).__name__}.")
    return dict(fields)


# ── uploads ────────────────────────────────────────────────────────────

# What uploads.create() reads: a file path, or the bytes themselves.
UploadSource = Union[str, "os.PathLike[str]", bytes]

UPLOAD_ATTEMPTS = 3  # tries per PUT to storage: a dropped connection or a 5xx from storage is retried
_UPLOAD_BACKOFF = 0.2  # seconds before the second try, doubled after
_CHUNK = 1024 * 1024  # bytes read from disk at a time, so a part is streamed, never held whole


def _file_path(file: Union[str, "os.PathLike[str]"]) -> str:
    """A path given as a str or an os.PathLike, as a str. Checked at run time too: the type check is the caller's to run."""
    try:
        path = os.fspath(file)
    except TypeError:
        raise InvalidArgumentError(f"file must be a path or bytes. Got {type(file).__name__}.") from None
    if not is_text(path):
        raise InvalidArgumentError(f"file must be a path given as text or bytes. Got the path {path!r}.")
    return path


class Source:
    """The bytes an upload sends: a file read in place (never loaded whole), or bytes in memory."""

    def __init__(self, file: UploadSource, filename: Optional[str]) -> None:
        self._data: Optional[bytes] = None
        self._path: Optional[str] = None
        if isinstance(file, bytes):
            self._data = file
            self.size = len(file)
            if filename is None:
                raise InvalidArgumentError("filename is required when uploading bytes: uploads.create(data, filename=\"clip.mp4\").")
        else:
            self._path = _file_path(file)
            try:
                self.size = os.path.getsize(self._path)
            except OSError as err:
                raise InvalidArgumentError(f"Cannot read {self._path!r}: {err.strerror or err}.") from None
        name = filename if filename is not None else os.path.basename(self._path or "")
        if not is_text(name) or not name:
            raise InvalidArgumentError(f"filename must be a non-empty string. Got {name!r}.")
        self.filename = name

    def chunks(self, offset: int, length: int) -> Generator[bytes, None, None]:
        """`length` bytes from `offset`, in pieces of at most 1 MiB."""
        if self._data is not None:
            yield self._data[offset:offset + length]
            return
        assert self._path is not None  # set whenever _data is not
        with open(self._path, "rb") as handle:
            handle.seek(offset)
            left = length
            while left > 0:
                block = handle.read(min(_CHUNK, left))
                if not block:
                    raise RendobarError(f"{self._path} got shorter while it was uploading.", code="UPLOAD_FAILED")
                left -= len(block)
                yield block


@dataclass(frozen=True)
class Part:
    """One part of a multipart upload: its 1-based number, where it starts, how long it is, and its presigned URL."""

    number: int
    offset: int
    length: int
    url: str


@dataclass(frozen=True)
class UploadPlan:
    """What POST /assets answered: nothing to send (`deduplicated`), one PUT (`presigned`), or parts (`multipart`)."""

    asset: Asset
    status: Literal["deduplicated", "presigned", "multipart"]
    parts: List[Part]


def _int(value: object) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def upload_plan(response: httpx.Response, size: int) -> UploadPlan:
    """Reads the upload init. Its body is not enveloped like the rest: `{status, data, upload}` at the top level."""
    try:
        decoded: object = response.json()
    except ValueError:
        decoded = response.text
    init = as_mapping(decoded)
    status = init.get("status") if init is not None else None
    upload = as_mapping(init.get("upload")) if init is not None else None
    try:
        asset = Asset.model_validate(init.get("data") if init is not None else None)
    except pydantic.ValidationError:
        raise unread(response, decoded) from None
    if status == "deduplicated":
        return UploadPlan(asset, "deduplicated", [])
    if status == "presigned" and upload is not None and isinstance(upload.get("url"), str):
        return UploadPlan(asset, "presigned", [Part(1, 0, size, str(upload["url"]))])
    part_size = _int(upload.get("partSize")) if upload is not None else None
    listed_parts = as_list(upload.get("parts")) if upload is not None else None
    if status == "multipart" and part_size is not None and part_size > 0 and listed_parts is not None:
        parts: List[Part] = []
        for item in listed_parts:
            part = as_mapping(item)
            number = _int(part.get("partNumber")) if part is not None else None
            url = part.get("url") if part is not None else None
            if number is None or number < 1 or not isinstance(url, str):
                raise unread(response, decoded)
            start = (number - 1) * part_size
            parts.append(Part(number, start, max(0, min(part_size, size - start)), url))
        return UploadPlan(asset, "multipart", parts)
    raise unread(response, decoded)


def upload_failed(status: int) -> RendobarError:
    return RendobarError(f"The upload to storage failed with status {status}.", code="UPLOAD_FAILED", status_code=status)


def missing_etag() -> RendobarError:
    # The storage took the part but did not say which version it stored, which completing the upload needs.
    return RendobarError("The storage answered a multipart part without an ETag header, so the upload cannot be completed.",
                         code="UPLOAD_FAILED", status_code=502)


def upload_pause(attempt: int) -> float:
    return _UPLOAD_BACKOFF * float(1 << attempt)


def upload_options(concurrency: int, on_progress: Optional[Callable[[UploadProgress], None]]) -> None:
    whole("concurrency", concurrency, 1)
    if on_progress is not None and not callable(on_progress):
        raise InvalidArgumentError("on_progress must be a function that takes an UploadProgress.")


def init_fields(source: Source, content_type: Optional[str], checksum: Optional[str], persist: bool) -> Dict[str, object]:
    text("content_type", content_type)
    text("checksum", checksum)
    flag("persist", persist)
    return {"contentType": content_type, "checksum": checksum, "lifecycle": "persisted" if persist else "ephemeral"}


def completed_parts(etags: Mapping[int, str]) -> List[Dict[str, object]]:
    return [{"partNumber": number, "etag": etags[number]} for number in sorted(etags)]


# ── the resources ──────────────────────────────────────────────────────


class Billing:
    """The workspace's balance, plan, usage, invoices and payment methods. Checkout and plan changes too."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.billing.with_raw_response

    def state(self) -> BillingState:
        """Balance, plan and its limits, subscription, this period's usage and any recurring top-up."""
        return self._client._read("GET", "/billing/state", self._raw.get_billing_state, one(BillingState))

    def usage(self, *, start: Optional[str] = None, end: Optional[str] = None) -> UsageSummary:
        """Jobs, spend and compute time between `start` and `end` (ISO dates, `"2026-11-01"`), by job type and by day."""
        text("start", start)
        text("end", end)
        return self._client._read("GET", "/billing/usage", lambda: self._raw.get_usage(start=start, end=end), one(UsageSummary))

    def usage_by_client(self, *, days: Optional[int] = None) -> List[ClientUsage]:
        """Usage over the last `days` (default 30), grouped by the client that submitted it (dashboard, python, cli, mcp, ...)."""
        lookback = usage_days(days)
        return self._client._read("GET", "/billing/usage-by-client", lambda: self._raw.get_usage_by_client(days=lookback),
                                  listed(ClientUsage))

    def transactions(self, *, page: Optional[int] = None, limit: Optional[int] = None) -> Page[Transaction, PageMeta]:
        """One page of credit transactions: top-ups, job charges and refunds, newest first. `page` counts from 1."""
        whole("page", page, 1)
        page_window(limit, None)
        return self._client._read("GET", "/billing/transactions", lambda: self._raw.list_transactions(page=page, limit=limit),
                                  paged(Transaction, PageMeta))

    def history(self, *, page: Optional[int] = None, limit: Optional[int] = None) -> Page[Invoice, PageMeta]:
        """One page of invoices, newest first. `page` counts from 1."""
        whole("page", page, 1)
        page_window(limit, None)
        return self._client._read("GET", "/billing/history", lambda: self._raw.list_invoices(page=page, limit=limit),
                                  paged(Invoice, PageMeta))

    def checkout_credits(self, amount: float, *, interval: Optional[CreditsInterval] = None) -> CreditsCheckout:
        """Start a credit purchase of `amount` US dollars: open `checkout_url`. `interval="month"` makes it a monthly top-up."""
        credit_amount(amount)
        return self._client._read("POST", "/billing/checkout/credits",
                                  lambda: self._raw.create_credits_checkout(amount=amount, request_options=body({"interval": interval})),
                                  one(CreditsCheckout))

    def checkout_plan(self, plan: PaidPlan) -> PlanCheckout:
        """Start a paid plan, such as `"pro"`.

        A workspace with no plan subscription gets a `PlanCheckoutStarted` to
        open (`checkout_url`). One already on another paid plan has it moved,
        billed pro rata, and gets a `PlanChanged`.
        """
        text("plan", plan)
        return self._client._read("POST", "/billing/checkout/plan", lambda: self._raw.create_plan_checkout(plan=plan), read_plan_checkout)

    def cancel_subscription(self) -> Subscription:
        """Cancel the plan at the end of the current period. Keeps the plan until then."""
        return self._client._read("PATCH", "/billing/subscription", lambda: self._raw.update_subscription(cancel_at_period_end=True),
                                  one(Subscription))

    def reactivate_subscription(self) -> Subscription:
        """Undo `cancel_subscription()` before the period ends."""
        return self._client._read("PATCH", "/billing/subscription", lambda: self._raw.update_subscription(cancel_at_period_end=False),
                                  one(Subscription))

    def cancel_credit_schedule(self) -> None:
        """Stop the recurring credit top-up at the end of the current period. The plan is not touched."""
        self._client._read("DELETE", "/billing/credit-schedule", self._raw.cancel_credit_schedule, empty)

    def payment_methods(self) -> List[PaymentMethod]:
        """The saved payment methods, with the default marked."""
        return self._client._read("GET", "/billing/payment-methods", self._raw.list_payment_methods, listed(PaymentMethod))

    def delete_payment_method(self, payment_method_id: str) -> None:
        """Remove a saved payment method."""
        safe = path_segment("payment_method_id", payment_method_id)
        self._client._read("DELETE", f"/billing/payment-methods/{safe}", lambda: self._raw.delete_payment_method(safe), empty)

    def set_default_payment_method(self, payment_method_id: str) -> DefaultPaymentMethod:
        """Make a saved payment method the one future charges use."""
        safe = path_segment("payment_method_id", payment_method_id)
        return self._client._read("PATCH", f"/billing/payment-methods/{safe}/default",
                                  lambda: self._raw.set_default_payment_method(safe), one(DefaultPaymentMethod))

    def portal_url(self) -> BillingPortal:
        """A link to the billing portal, where payment methods and invoices are managed."""
        return self._client._read("GET", "/billing/payment-methods/portal-url", self._raw.get_billing_portal_url, one(BillingPortal))


class Uploads:
    """Upload a local file as an asset, to use as a job input (`asset://<id>`)."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.assets.with_raw_response

    def create(
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
        """Upload `file` and return the ready asset. Reference it in a job as `asset://<asset.id>`.

        The bytes go straight to storage on presigned URLs: one PUT for a file
        up to the API's single-upload size, or parts in parallel for a larger
        one. A file on disk is streamed, never read into memory whole.

        Args:
            file: A file path, or the bytes to upload.
            filename: The name the asset gets. Default: the file's own name. Required for bytes.
            content_type: The MIME type, such as `"video/mp4"`.
            checksum: The file's SHA-256 in hex. A ready asset with the same checksum is returned
                instead of uploading again.
            persist: Keep the asset until you delete it. Default: it expires on its own after 24 hours.
            concurrency: How many parts of a large file upload at once.
            on_progress: Called with an `UploadProgress` as each part finishes.
        """
        source = Source(file, filename)
        upload_options(concurrency, on_progress)
        fields = init_fields(source, content_type, checksum, persist)
        plan = self._client._read("POST", "/assets", lambda: self._raw.create_asset(
            filename=source.filename, size=source.size, request_options=body(fields)), lambda response: upload_plan(response, source.size))
        progress = _Progress(source.size, on_progress)
        if plan.status == "deduplicated":
            progress.add(source.size)
            return plan.asset
        safe = path_segment("asset id", plan.asset.id)
        if plan.status == "presigned":
            self._put(source, plan.parts[0])
            progress.add(source.size)
            return self._client._read("POST", f"/assets/{safe}/complete", lambda: self._raw.complete_asset_upload(safe), one(Asset))
        etags = self._parts(source, plan.parts, concurrency, progress)
        return self._client._read("POST", f"/assets/{safe}/complete", lambda: self._raw.complete_asset_upload(
            safe, request_options=body({"parts": completed_parts(etags)})), one(Asset))

    def _parts(self, source: Source, parts: Sequence[Part], concurrency: int, progress: _Progress) -> Dict[int, str]:
        etags: Dict[int, str] = {}

        def send(part: Part) -> None:
            etag = self._put(source, part)
            if etag is None:
                raise missing_etag()
            etags[part.number] = etag
            progress.add(part.length)

        with ThreadPoolExecutor(max_workers=max(1, min(concurrency, len(parts)))) as pool:
            futures: List[Future[None]] = [pool.submit(send, part) for part in parts]
            done, _ = wait(futures, return_when=FIRST_EXCEPTION)
            failed = next((future for future in done if future.exception() is not None), None)
            if failed is not None:
                for future in futures:
                    future.cancel()  # parts not started yet are not sent
                error = failed.exception()
                assert error is not None
                raise error
        return etags

    def _put(self, source: Source, part: Part) -> Optional[str]:
        """PUT one part to its presigned URL and return the ETag storage answered with (None when it sent none)."""
        last: Optional[RendobarError] = None
        for attempt in range(UPLOAD_ATTEMPTS):
            if attempt:
                time.sleep(upload_pause(attempt - 1))
            try:
                response = self._client._http.put(part.url, content=source.chunks(part.offset, part.length),
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


class _Progress:
    """Adds finished bytes and reports them. Parts finish on worker threads, so the count is locked."""

    def __init__(self, total: int, report: Optional[Callable[[UploadProgress], None]]) -> None:
        self._total = total
        self._loaded = 0
        self._report = report
        self._lock = threading.Lock()

    def add(self, size: int) -> None:
        with self._lock:
            self._loaded = min(self._total, self._loaded + size)
            loaded = self._loaded
        if self._report is not None:
            self._report(UploadProgress(loaded, self._total))


class Assets:
    """Files in the workspace: uploads, job outputs kept as assets, and templates."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.assets.with_raw_response

    def list(
        self,
        *,
        kind: Optional[AssetKind] = None,
        scope: Optional[AssetScope] = None,
        status: Optional[AssetStatus] = None,
        lifecycle: Optional[AssetLifecycle] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Page[Asset, OffsetPageMeta]:
        """One page of assets, newest first, filtered by `kind`, `scope`, `status` and `lifecycle`."""
        page_window(limit, offset)
        return self._client._read("GET", "/assets", lambda: self._raw.list_assets(
            kind=kind, scope=scope, status=status, lifecycle=lifecycle, limit=limit, offset=offset), paged(Asset, OffsetPageMeta))

    def get(self, asset_id: str) -> Asset:
        safe = path_segment("asset_id", asset_id)
        return self._client._read("GET", f"/assets/{safe}", lambda: self._raw.get_asset(safe), one(Asset))

    def delete(self, asset_id: str) -> AssetDeleted:
        """Delete an asset and its file."""
        safe = path_segment("asset_id", asset_id)
        return self._client._read("DELETE", f"/assets/{safe}", lambda: self._raw.delete_asset(safe), one(AssetDeleted))

    def download(self, asset_id: str) -> AssetDownload:
        """A short-lived URL to the asset's file, and when it expires (`expires_at`, Unix ms)."""
        safe = path_segment("asset_id", asset_id)
        return self._client._read("GET", f"/assets/{safe}/download", lambda: self._raw.download_asset(safe), one(AssetDownload))

    def templates(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> Page[Asset, OffsetPageMeta]:
        """One page of the template assets every workspace can use."""
        page_window(limit, offset)
        return self._client._read("GET", "/assets/templates", lambda: self._raw.list_asset_templates(limit=limit, offset=offset),
                                  paged(Asset, OffsetPageMeta))


class Webhooks:
    """Webhook endpoints Rendobar delivers job and balance events to, and the record of each delivery.

    To read a delivery your server received, use `rendobar.webhooks.parse()`.
    """

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.webhooks.with_raw_response

    def create(self, *, name: str, url: str, subscribed_events: List[WebhookEventType]) -> WebhookEndpointWithSecret:
        """Add an endpoint. The answer holds `signing_secret` in plaintext, the only time but rotate: store it."""
        text("name", name)
        text("url", url)
        texts("subscribed_events", subscribed_events)
        return self._client._read("POST", "/webhooks/endpoints", lambda: self._raw.create_webhook_endpoint(
            name=name, url=url, subscribed_events=subscribed_events), one(WebhookEndpointWithSecret))

    def list(self) -> Page[WebhookEndpoint, ListMeta]:
        """Every endpoint, with its secret masked."""
        return self._client._read("GET", "/webhooks/endpoints", self._raw.list_webhook_endpoints, paged(WebhookEndpoint, ListMeta))

    def get(self, endpoint_id: str) -> WebhookEndpoint:
        safe = path_segment("endpoint_id", endpoint_id)
        return self._client._read("GET", f"/webhooks/endpoints/{safe}", lambda: self._raw.get_webhook_endpoint(safe), one(WebhookEndpoint))

    def update(
        self,
        endpoint_id: str,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        subscribed_events: Optional[List[WebhookEventType]] = None,
        active: Optional[bool] = None,
    ) -> WebhookEndpoint:
        """Change what is passed and leave the rest. `active=False` pauses deliveries."""
        safe = path_segment("endpoint_id", endpoint_id)
        text("name", name)
        text("url", url)
        flag("active", active)
        events = None if subscribed_events is None else texts("subscribed_events", subscribed_events)
        fields = {"name": name, "url": url, "subscribedEvents": events, "active": active}
        return self._client._read("PATCH", f"/webhooks/endpoints/{safe}",
                                  lambda: self._raw.update_webhook_endpoint(safe, request_options=body(fields)), one(WebhookEndpoint))

    def delete(self, endpoint_id: str) -> None:
        safe = path_segment("endpoint_id", endpoint_id)
        self._client._read("DELETE", f"/webhooks/endpoints/{safe}", lambda: self._raw.delete_webhook_endpoint(safe), empty)

    def rotate_secret(self, endpoint_id: str) -> WebhookEndpointWithSecret:
        """A new signing secret, in plaintext. For 24 hours deliveries carry both signatures, so receivers can switch."""
        safe = path_segment("endpoint_id", endpoint_id)
        return self._client._read("POST", f"/webhooks/endpoints/{safe}/secret", lambda: self._raw.rotate_webhook_secret(safe),
                                  one(WebhookEndpointWithSecret))

    def test(self, endpoint_id: str) -> WebhookTestResult:
        """Send a `test` event now and report whether the endpoint answered with a 2xx."""
        safe = path_segment("endpoint_id", endpoint_id)
        return self._client._read("POST", f"/webhooks/endpoints/{safe}/test", lambda: self._raw.test_webhook_endpoint(safe),
                                  one(WebhookTestResult))

    def list_deliveries(
        self,
        *,
        endpoint_id: Optional[str] = None,
        event: Optional[str] = None,
        status: Optional[WebhookDeliveryStatus] = None,
        job_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Page[WebhookDelivery, DeliveriesPageMeta]:
        """One page of delivery records, newest first, filtered by endpoint, event name, status or job."""
        page_window(limit, offset)
        for name, value in (("endpoint_id", endpoint_id), ("event", event), ("job_id", job_id)):
            text(name, value)
        return self._client._read("GET", "/webhooks/deliveries", lambda: self._raw.list_webhook_deliveries(
            endpoint_id=endpoint_id, event=event, status=status, job_id=job_id, limit=limit, offset=offset),
            paged(WebhookDelivery, DeliveriesPageMeta))

    def retry_delivery(self, delivery_id: str) -> RetriedDelivery:
        """Send a failed or cancelled delivery again."""
        safe = path_segment("delivery_id", delivery_id)
        return self._client._read("POST", f"/webhooks/deliveries/{safe}/retry", lambda: self._raw.retry_webhook_delivery(safe),
                                  one(RetriedDelivery))


class Storage:
    """Buckets you own, connected once under an id you choose, then used as `storage://<id>/...`.

    Credentials are checked before they are stored and never come back in any response.
    """

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.storage.with_raw_response

    def create(self, params: StorageCreate) -> StorageConnection:
        """Connect a bucket, with the checks that admitted it in `checks`.

        `params` is one dict per `provider` (`"s3"`, `"r2"`, `"s3-compatible"`,
        `"supabase"`). Raises BadRequestError when the write check fails and
        ConflictError when the id is taken.
        """
        request = storage_create(params)
        return self._client._read("POST", "/storage", lambda: self._raw.create_storage(request=request), one(StorageConnection))

    def list(self) -> Page[StorageConnection, ListMeta]:
        return self._client._read("GET", "/storage", self._raw.list_storage, paged(StorageConnection, ListMeta))

    def get(self, storage_id: str) -> StorageConnection:
        safe = path_segment("storage_id", storage_id)
        return self._client._read("GET", f"/storage/{safe}", lambda: self._raw.get_storage(safe), one(StorageConnection))

    def update(
        self,
        storage_id: str,
        *,
        credentials: Optional[StorageCredentials] = None,
        public_base_url: Optional[str] = None,
        path_template: Optional[str] = None,
        on_conflict: Optional[StorageConflict] = None,
        default_destination: Optional[bool] = None,
    ) -> StorageConnection:
        """Rotate the credentials (checked first) or change how outputs are written. Leaves what is not passed."""
        safe = path_segment("storage_id", storage_id)
        text("public_base_url", public_base_url)
        text("path_template", path_template)
        flag("default_destination", default_destination)
        fields = {"credentials": storage_credentials(credentials), "publicBaseUrl": public_base_url, "pathTemplate": path_template,
                  "onConflict": on_conflict, "defaultDestination": default_destination}
        return self._client._read("PATCH", f"/storage/{safe}", lambda: self._raw.update_storage(safe, request_options=body(fields)),
                                  one(StorageConnection))

    def delete(self, storage_id: str) -> None:
        safe = path_segment("storage_id", storage_id)
        self._client._read("DELETE", f"/storage/{safe}", lambda: self._raw.delete_storage(safe), empty)

    def test(self, storage_id: str) -> StorageTestResult:
        """Write, read, list and delete a probe object. `ok` reflects the write check."""
        safe = path_segment("storage_id", storage_id)
        return self._client._read("POST", f"/storage/{safe}/test", lambda: self._raw.test_storage(safe), one(StorageTestResult))

    def stats(self, storage_id: str) -> StorageActivity:
        """What the connection has been doing: deliveries a day, throughput and bytes written. Never an object name."""
        safe = path_segment("storage_id", storage_id)
        return self._client._read("GET", f"/storage/{safe}/stats", lambda: self._raw.get_storage_stats(safe), one(StorageActivity))

    def list_objects(self, storage_id: str, *, prefix: Optional[str] = None, cursor: Optional[str] = None,
                     limit: Optional[int] = None) -> StorageObjects:
        """One page of the folders and files directly under `prefix` (a folder ending in `/`). Pass `cursor` for the next page."""
        safe = path_segment("storage_id", storage_id)
        text("prefix", prefix)
        text("cursor", cursor)
        page_window(limit, None)
        # An empty prefix is the root and an empty cursor the first page: neither goes on the wire.
        return self._client._read("GET", f"/storage/{safe}/objects", lambda: self._raw.list_storage_objects(
            safe, prefix=prefix or None, cursor=cursor or None, limit=limit), one(StorageObjects))

    def prepare_aws(
        self,
        *,
        id: str,
        bucket: str,
        region: Optional[str] = None,
        public_base_url: Optional[str] = None,
        create_bucket: Optional[bool] = None,
        access: Optional[AwsAccess] = None,
    ) -> PreparedAwsStorage:
        """Start connecting an S3 bucket with one click: a pending connection and a CloudFormation quick-create link.

        The stack reports back and the connection finishes on its own: poll
        `get(id)` until `pending` is gone.
        """
        for name, value in (("id", id), ("bucket", bucket), ("region", region), ("public_base_url", public_base_url)):
            text(name, value)
        flag("create_bucket", create_bucket)
        fields = {"region": region, "publicBaseUrl": public_base_url, "createBucket": create_bucket, "access": access}
        return self._client._read("POST", "/storage/aws/prepare", lambda: self._raw.prepare_aws_storage(
            id=id, bucket=bucket, request_options=body(fields)), one(PreparedAwsStorage))

    def list_account_buckets(self, *, provider: BucketProvider = "s3") -> AccountBuckets:
        """The bucket names a connection this workspace already has on `provider` can see. Empty when there is none."""
        return self._client._read("GET", "/storage/buckets", lambda: self._raw.list_account_buckets(provider=provider), one(AccountBuckets))

    def look_up_s3_bucket(self, name: str) -> S3BucketLookup:
        """Whether an S3 bucket name is taken, and in which region. It cannot say whether the bucket is yours."""
        text("name", name)
        return self._client._read("GET", "/storage/s3/bucket", lambda: self._raw.look_up_s3bucket(name=name), one(S3BucketLookup))

    def start_supabase(self) -> SupabaseSignIn:
        """Sign in with Supabase: where to send the person, who comes back with the `state`."""
        return self._client._read("POST", "/storage/supabase/start", self._raw.start_supabase_storage, one(SupabaseSignIn))

    def list_supabase_projects(self, state: str) -> SupabaseProjects:
        """The projects a Supabase sign-in can see."""
        safe = path_segment("state", state)
        return self._client._read("GET", f"/storage/supabase/sessions/{safe}", lambda: self._raw.get_supabase_session(safe),
                                  one(SupabaseProjects))

    def list_supabase_buckets(self, state: str, project_ref: str) -> SupabaseBuckets:
        """The buckets one of those projects has."""
        session = path_segment("state", state)
        project = path_segment("project_ref", project_ref)
        return self._client._read("GET", f"/storage/supabase/sessions/{session}/projects/{project}/buckets",
                                  lambda: self._raw.list_supabase_buckets(session, project), one(SupabaseBuckets))

    def finish_supabase(
        self,
        *,
        state: str,
        project_ref: str,
        id: str,
        bucket: str,
        public_base_url: Optional[str] = None,
        create_bucket: Optional[bool] = None,
    ) -> StorageConnection:
        """Finish a Supabase sign-in as one connection. Raises BadRequestError when it expired or the checks failed."""
        for name, value in (("state", state), ("project_ref", project_ref), ("id", id), ("bucket", bucket),
                            ("public_base_url", public_base_url)):
            text(name, value)
        flag("create_bucket", create_bucket)
        fields = {"publicBaseUrl": public_base_url, "createBucket": create_bucket}
        return self._client._read("POST", "/storage/supabase/finish", lambda: self._raw.finish_supabase_storage(
            state=state, project_ref=project_ref, id=id, bucket=bucket, request_options=body(fields)), one(StorageConnection))


class ApiKeys:
    """The workspace's API keys."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.api_keys.with_raw_response

    def create(self, *, name: Optional[str] = None, expires_in: Optional[int] = None,
               scopes: Optional[List[str]] = None) -> CreatedApiKey:
        """A new key. Its value is in `key`, shown only here: store it.

        Args:
            name: What the key is for.
            expires_in: Seconds until it stops working. Default: never.
            scopes: What it may do, such as `["jobs:read"]`. Default: everything
                your role can grant. Asking for more is refused, not narrowed.

        Creating a key needs the `keys:write` scope, which no API key holds:
        with an API key this raises PermissionDeniedError. An OAuth token or a
        dashboard session can.
        """
        text("name", name)
        whole("expires_in", expires_in, 1)
        granted = None if scopes is None else texts("scopes", scopes)
        return self._client._read("POST", "/api-keys", lambda: self._raw.create_api_key(
            request_options=body({"name": name, "expiresIn": expires_in, "scopes": granted})), one(CreatedApiKey))

    def list(self) -> List[ApiKey]:
        return self._client._read("GET", "/api-keys", self._raw.list_api_keys, listed(ApiKey))

    def revoke(self, key_id: str) -> ApiKeyRevoked:
        """Turn a key off for good."""
        safe = path_segment("key_id", key_id)
        return self._client._read("DELETE", f"/api-keys/{safe}", lambda: self._raw.revoke_api_key(safe), one(ApiKeyRevoked))

    def update(self, key_id: str, *, name: Optional[str] = None, enabled: Optional[bool] = None) -> ApiKey:
        """Rename a key, or switch it off and on. Needs the Admin or Owner role."""
        safe = path_segment("key_id", key_id)
        text("name", name)
        flag("enabled", enabled)
        return self._client._read("PATCH", f"/api-keys/{safe}", lambda: self._raw.update_api_key(
            safe, request_options=body({"name": name, "enabled": enabled})), one(ApiKey))


class Members:
    """The current organization's members. Inviting and changing roles needs the Owner or Admin role."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response

    def invite(self, *, email: str, role: InviteRole) -> Invitation:
        """Invite someone to the current organization by email, with the role they get when they accept."""
        text("email", email)
        return self._client._read("POST", "/orgs/current/members", lambda: self._raw.invite_org_member(email=email, role=role),
                                  one(Invitation))

    def change_role(self, member_id: str, *, role: MemberRole) -> MemberRoleChanged:
        safe = path_segment("member_id", member_id)
        return self._client._read("PATCH", f"/orgs/current/members/{safe}",
                                  lambda: self._raw.update_org_member_role(safe, role=role), one(MemberRoleChanged))

    def remove(self, member_id: str) -> MemberRemoved:
        """Remove a member, or pass your own member id to leave."""
        safe = path_segment("member_id", member_id)
        return self._client._read("DELETE", f"/orgs/current/members/{safe}", lambda: self._raw.remove_org_member(safe),
                                  one(MemberRemoved))


class Invitations:
    """Pending invitations to the current organization."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response

    def revoke(self, invitation_id: str) -> InvitationRevoked:
        """Cancel a pending invitation. Needs the Owner or Admin role."""
        safe = path_segment("invitation_id", invitation_id)
        return self._client._read("DELETE", f"/orgs/current/invitations/{safe}", lambda: self._raw.revoke_org_invitation(safe),
                                  one(InvitationRevoked))


class Orgs:
    """The organizations you belong to, and the current one: its settings, members and invitations."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.organizations.with_raw_response
        self.members = Members(client)
        self.invitations = Invitations(client)

    def list(self) -> List[OrgMembership]:
        """Every organization you belong to, with your role in each."""
        return self._client._read("GET", "/orgs", self._raw.list_orgs, listed(OrgMembership))

    def current(self) -> CurrentOrg:
        """The organization this key belongs to, with its subscription, plan limits and balance."""
        return self._client._read("GET", "/orgs/current", self._raw.get_current_org, one(CurrentOrg))

    def create(self, *, name: str, slug: str) -> NewOrganization:
        text("name", name)
        text("slug", slug)
        return self._client._read("POST", "/orgs", lambda: self._raw.create_org(name=name, slug=slug), one(NewOrganization))

    def update(self, *, name: Optional[str] = None, slug: Optional[str] = None) -> Organization:
        """Rename the current organization or change its slug."""
        text("name", name)
        text("slug", slug)
        return self._client._read("PATCH", "/orgs/current", lambda: self._raw.update_org(request_options=body({"name": name, "slug": slug})),
                                  one(Organization))

    def delete(self) -> None:
        """Delete the current organization. Needs the Owner role. Cannot be undone."""
        self._client._read("DELETE", "/orgs/current", self._raw.delete_org, empty)

    def get_settings(self) -> OrgSettings:
        return self._client._read("GET", "/orgs/current/settings", self._raw.get_org_settings, one(OrgSettings))

    def update_settings(
        self,
        *,
        billing_emails_enabled: Optional[bool] = None,
        default_region: Optional[Region] = None,
        region_pinned: Optional[bool] = None,
        product_analytics_enabled: Optional[bool] = None,
    ) -> OrgSettings:
        """Change the settings passed and leave the rest. Returns every setting as it now is."""
        for name, value in (("billing_emails_enabled", billing_emails_enabled), ("region_pinned", region_pinned),
                            ("product_analytics_enabled", product_analytics_enabled)):
            flag(name, value)
        fields = {"billingEmailsEnabled": billing_emails_enabled, "defaultRegion": default_region, "regionPinned": region_pinned,
                  "productAnalyticsEnabled": product_analytics_enabled}
        return self._client._read("PATCH", "/orgs/current/settings", lambda: self._raw.update_org_settings(request_options=body(fields)),
                                  one(OrgSettings))


class Compose:
    """Helpers for the compose job that render nothing."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.compose.with_raw_response

    def effects(self) -> ComposeEffects:
        """Every built-in effect, with its parameters, ranges, units, defaults and which take keyframes."""
        return self._client._read("GET", "/compose/effects", self._raw.list_compose_effects, one(ComposeEffects))

    def engine_effects(self) -> ComposeEngineEffects:
        """Every filter an `engine` effect may name, with its parameters. A filter a built-in effect covers is not listed."""
        return self._client._read("GET", "/compose/effects/engine", self._raw.list_compose_engine_effects, one(ComposeEngineEffects))

    def validate(self, params: Mapping[str, object]) -> ComposeValidation:
        """Check compose params without rendering them. Free, and nothing is stored.

        Pass what you would pass as the compose job's `params`. A `ComposeValid`
        carries them as a render would read them (defaults filled in, an older
        timeline shape rewritten, named in `upgraded`) and the `price`. A
        `ComposeInvalid` carries the `problems`. Validating changes nothing, so
        a failed request is retried like a read.
        """
        document = compose_params(params)
        return self._client._read("POST", "/compose/validate", lambda: self._raw.validate_compose(params=document),
                                  read_compose_validation, replayable=True)


class Notifications:
    """The workspace's notifications, with your read state."""

    def __init__(self, client: Rendobar) -> None:
        self._client = client
        self._raw = client._core.notifications.with_raw_response

    def list(self) -> Page[Notification, NotificationsMeta]:
        """The newest 50 notifications, and how many are unread (`meta.unread`)."""
        return self._client._read("GET", "/notifications", self._raw.list_notifications, paged(Notification, NotificationsMeta))

    def mark_read(self, ids: List[str]) -> NotificationsRead:
        """Mark notifications read for you. Ids that do not exist are ignored."""
        chosen = texts("ids", ids)
        return self._client._read("POST", "/notifications/read", lambda: self._raw.mark_notifications_read(ids=chosen),
                                  one(NotificationsRead), replayable=True)

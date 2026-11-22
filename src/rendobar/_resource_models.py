"""Public names for what the account, billing, upload, asset, webhook, storage, key,
organization, compose and notification methods return and take.

The generated core inlines each operation's response, so one resource comes
back as a different class from get, list and update (`GetStorageResponseData`,
`ListStorageResponseDataItem`, ...). Each resource here has ONE public model:
the readers in `_plumbing` parse every operation's body into it, so a storage
connection is a `StorageConnection` whichever method returned it. As in
`_models`, `publish` gives each class its public name without editing
`_generated`, and a regeneration that renames or drops a model fails the
import here, in CI.

Enums a response carries are `Literal[...] | str` (fern/postprocess.py), so a
value newer than this SDK still parses. Enums a request takes are closed, so a
misspelt value fails the type check.
"""
# pyright: strict
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type, Union

from ._generated.api_keys.types.create_api_key_response_data import CreateApiKeyResponseData
from ._generated.api_keys.types.revoke_api_key_response_data import RevokeApiKeyResponseData
from ._generated.assets.types.delete_asset_response_data import DeleteAssetResponseData
from ._generated.assets.types.download_asset_response_data import DownloadAssetResponseData
from ._generated.assets.types.get_asset_response_data import GetAssetResponseData
from ._generated.assets.types.list_assets_request_kind import ListAssetsRequestKind
from ._generated.assets.types.list_assets_request_lifecycle import ListAssetsRequestLifecycle
from ._generated.assets.types.list_assets_request_scope import ListAssetsRequestScope
from ._generated.assets.types.list_assets_request_status import ListAssetsRequestStatus
from ._generated.assets.types.list_assets_response_meta import ListAssetsResponseMeta
from ._generated.billing.types.create_credits_checkout_request_interval import CreateCreditsCheckoutRequestInterval
from ._generated.billing.types.create_credits_checkout_response_data import CreateCreditsCheckoutResponseData
from ._generated.billing.types.create_plan_checkout_request_plan import CreatePlanCheckoutRequestPlan
from ._generated.billing.types.create_plan_checkout_response_data import (
    CreatePlanCheckoutResponseData_Changed,
    CreatePlanCheckoutResponseData_Checkout,
)
from ._generated.billing.types.get_billing_portal_url_response_data import GetBillingPortalUrlResponseData
from ._generated.billing.types.get_billing_state_response_data import GetBillingStateResponseData
from ._generated.billing.types.get_usage_by_client_response_data_item import GetUsageByClientResponseDataItem
from ._generated.billing.types.get_usage_response_data import GetUsageResponseData
from ._generated.billing.types.list_invoices_response_data_item import ListInvoicesResponseDataItem
from ._generated.billing.types.list_payment_methods_response_data_item import ListPaymentMethodsResponseDataItem
from ._generated.billing.types.list_transactions_response_data_item import ListTransactionsResponseDataItem
from ._generated.billing.types.set_default_payment_method_response_data import SetDefaultPaymentMethodResponseData
from ._generated.billing.types.update_subscription_response_data import UpdateSubscriptionResponseData
from ._generated.compose.types.list_compose_effects_response_data import ListComposeEffectsResponseData
from ._generated.compose.types.list_compose_engine_effects_response_data import ListComposeEngineEffectsResponseData
from ._generated.compose.types.validate_compose_response_data_price import ValidateComposeResponseDataPrice
from ._generated.compose.types.validate_compose_response_data_problems import ValidateComposeResponseDataProblems
from ._generated.jobs.types.get_job_logs_response_data_item import GetJobLogsResponseDataItem
from ._generated.jobs.types.get_job_stats_request_window import GetJobStatsRequestWindow
from ._generated.jobs.types.get_job_stats_response_data import GetJobStatsResponseData
from ._generated.jobs.types.get_job_timings_response_data import GetJobTimingsResponseData
from ._generated.jobs.types.list_jobs_request_order import ListJobsRequestOrder
from ._generated.jobs.types.list_jobs_request_sort import ListJobsRequestSort
from ._generated.jobs.types.retry_deliveries_response_data import RetryDeliveriesResponseData
from ._generated.notifications.types.list_notifications_response_data_item import ListNotificationsResponseDataItem
from ._generated.notifications.types.list_notifications_response_meta import ListNotificationsResponseMeta
from ._generated.notifications.types.mark_notifications_read_response_data import MarkNotificationsReadResponseData
from ._generated.organizations.types.create_org_response_data import CreateOrgResponseData
from ._generated.organizations.types.get_current_org_response_data import GetCurrentOrgResponseData
from ._generated.organizations.types.get_org_settings_response_data import GetOrgSettingsResponseData
from ._generated.organizations.types.invite_org_member_request_role import InviteOrgMemberRequestRole
from ._generated.organizations.types.invite_org_member_response_data import InviteOrgMemberResponseData
from ._generated.organizations.types.list_orgs_response_data_item import ListOrgsResponseDataItem
from ._generated.organizations.types.remove_org_member_response_data import RemoveOrgMemberResponseData
from ._generated.organizations.types.revoke_org_invitation_response_data import RevokeOrgInvitationResponseData
from ._generated.organizations.types.update_org_member_role_request_role import UpdateOrgMemberRoleRequestRole
from ._generated.organizations.types.update_org_member_role_response_data import UpdateOrgMemberRoleResponseData
from ._generated.organizations.types.update_org_response_data import UpdateOrgResponseData
from ._generated.organizations.types.update_org_settings_request_default_region import UpdateOrgSettingsRequestDefaultRegion
from ._generated.storage.requests.create_storage_request import CreateStorageRequestParams
from ._generated.storage.requests.update_storage_request_credentials import UpdateStorageRequestCredentialsParams
from ._generated.storage.types.get_storage_response_data import GetStorageResponseData
from ._generated.storage.types.get_storage_stats_response_data import GetStorageStatsResponseData
from ._generated.storage.types.get_supabase_session_response_data import GetSupabaseSessionResponseData
from ._generated.storage.types.list_account_buckets_request_provider import ListAccountBucketsRequestProvider
from ._generated.storage.types.list_account_buckets_response_data import ListAccountBucketsResponseData
from ._generated.storage.types.list_storage_objects_response_data import ListStorageObjectsResponseData
from ._generated.storage.types.list_supabase_buckets_response_data import ListSupabaseBucketsResponseData
from ._generated.storage.types.look_up_s3bucket_response_data import LookUpS3BucketResponseData
from ._generated.storage.types.prepare_aws_storage_request_access import PrepareAwsStorageRequestAccess
from ._generated.storage.types.prepare_aws_storage_response_data import PrepareAwsStorageResponseData
from ._generated.storage.types.start_supabase_storage_response_data import StartSupabaseStorageResponseData
from ._generated.storage.types.test_storage_response_data import TestStorageResponseData
from ._generated.storage.types.update_storage_request_on_conflict import UpdateStorageRequestOnConflict
from ._generated.types.api_key import ApiKey
from ._generated.types.webhook_endpoint import WebhookEndpoint
from ._generated.webhooks.types.create_webhook_endpoint_request_subscribed_events_item import (
    CreateWebhookEndpointRequestSubscribedEventsItem,
)
from ._generated.webhooks.types.create_webhook_endpoint_response_data import CreateWebhookEndpointResponseData
from ._generated.webhooks.types.list_webhook_deliveries_request_status import ListWebhookDeliveriesRequestStatus
from ._generated.webhooks.types.list_webhook_deliveries_response_data_item import ListWebhookDeliveriesResponseDataItem
from ._generated.webhooks.types.list_webhook_deliveries_response_meta import ListWebhookDeliveriesResponseMeta
from ._generated.webhooks.types.list_webhook_endpoints_response_meta import ListWebhookEndpointsResponseMeta
from ._generated.webhooks.types.retry_webhook_delivery_response_data import RetryWebhookDeliveryResponseData
from ._generated.webhooks.types.test_webhook_endpoint_response_data import TestWebhookEndpointResponseData
from ._models import publish

__all__ = [
    # lists
    "OffsetPageMeta", "DeliveriesPageMeta", "ListMeta",
    # jobs
    "JobLogEntry", "JobTimings", "JobStats", "StatsWindow", "JobSort", "SortOrder", "DeliveriesRetried",
    # billing
    "BillingState", "UsageSummary", "ClientUsage", "Transaction", "Invoice", "CreditsCheckout", "CreditsInterval",
    "PlanCheckout", "PlanCheckoutStarted", "PlanChanged", "PaidPlan", "Subscription", "PaymentMethod",
    "DefaultPaymentMethod", "BillingPortal",
    # uploads and assets
    "Asset", "AssetDownload", "AssetDeleted", "AssetKind", "AssetScope", "AssetStatus", "AssetLifecycle", "UploadProgress",
    # webhooks
    "WebhookEndpoint", "WebhookEndpointWithSecret", "WebhookTestResult", "WebhookDelivery", "WebhookDeliveryStatus",
    "RetriedDelivery", "WebhookEventType",
    # storage
    "StorageConnection", "StorageCreate", "StorageCredentials", "StorageConflict", "StorageTestResult",
    "StorageActivity", "StorageObjects", "PreparedAwsStorage", "AwsAccess", "AccountBuckets", "BucketProvider",
    "S3BucketLookup", "SupabaseSignIn", "SupabaseProjects", "SupabaseBuckets",
    # API keys
    "ApiKey", "CreatedApiKey", "ApiKeyRevoked",
    # organizations
    "OrgMembership", "CurrentOrg", "NewOrganization", "Organization", "OrgSettings", "Region", "Invitation",
    "InviteRole", "MemberRole", "MemberRoleChanged", "MemberRemoved", "InvitationRevoked",
    # compose
    "ComposeEffects", "ComposeEngineEffects", "ComposeValidation", "ComposeValid", "ComposeInvalid",
    # notifications
    "Notification", "NotificationsMeta", "NotificationsRead",
    "RESOURCE_MODELS",
]

# ── list metadata ──────────────────────────────────────────────────────
# Lists paged by offset report `total`, `limit` and `offset`; jobs, transactions
# and invoices by page report `total`, `page` and `limit` (`PageMeta`, in _models).
OffsetPageMeta = ListAssetsResponseMeta
ListMeta = ListWebhookEndpointsResponseMeta  # a list that is not paged: its `total`
# webhooks.list_deliveries(): the spec types its `offset` as a number, not an integer.
DeliveriesPageMeta = ListWebhookDeliveriesResponseMeta

# ── jobs ───────────────────────────────────────────────────────────────
JobLogEntry = GetJobLogsResponseDataItem
JobTimings = GetJobTimingsResponseData
JobStats = GetJobStatsResponseData
StatsWindow = GetJobStatsRequestWindow  # jobs.stats(window=...)
JobSort = ListJobsRequestSort  # jobs.list(sort=...)
SortOrder = ListJobsRequestOrder  # jobs.list(order=...)
DeliveriesRetried = RetryDeliveriesResponseData

# ── billing ────────────────────────────────────────────────────────────
BillingState = GetBillingStateResponseData
UsageSummary = GetUsageResponseData
ClientUsage = GetUsageByClientResponseDataItem
Transaction = ListTransactionsResponseDataItem
Invoice = ListInvoicesResponseDataItem
CreditsCheckout = CreateCreditsCheckoutResponseData
CreditsInterval = CreateCreditsCheckoutRequestInterval  # billing.checkout_credits(interval=...)
PaidPlan = CreatePlanCheckoutRequestPlan  # billing.checkout_plan(plan)
# What billing.checkout_plan() returns: a checkout to open, or a plan changed in place.
PlanCheckoutStarted = CreatePlanCheckoutResponseData_Checkout
PlanChanged = CreatePlanCheckoutResponseData_Changed
PlanCheckout = Union[PlanCheckoutStarted, PlanChanged]
Subscription = UpdateSubscriptionResponseData
PaymentMethod = ListPaymentMethodsResponseDataItem
DefaultPaymentMethod = SetDefaultPaymentMethodResponseData
BillingPortal = GetBillingPortalUrlResponseData

# ── uploads and assets ─────────────────────────────────────────────────
Asset = GetAssetResponseData
AssetDownload = DownloadAssetResponseData
AssetDeleted = DeleteAssetResponseData
AssetKind = ListAssetsRequestKind
AssetScope = ListAssetsRequestScope
AssetStatus = ListAssetsRequestStatus
AssetLifecycle = ListAssetsRequestLifecycle


@dataclass(frozen=True)
class UploadProgress:
    """How much of an upload is done: `loaded` of `total` bytes. Passed to `uploads.create(on_progress=...)`."""

    loaded: int
    total: int


# ── webhooks ───────────────────────────────────────────────────────────
# `signing_secret` of a WebhookEndpoint is masked. Only create and rotate_secret return it in
# plaintext, as a WebhookEndpointWithSecret: store it then, it is not shown again.
WebhookEndpointWithSecret = CreateWebhookEndpointResponseData
WebhookTestResult = TestWebhookEndpointResponseData
WebhookDelivery = ListWebhookDeliveriesResponseDataItem
WebhookDeliveryStatus = ListWebhookDeliveriesRequestStatus  # webhooks.list_deliveries(status=...)
RetriedDelivery = RetryWebhookDeliveryResponseData
WebhookEventType = CreateWebhookEndpointRequestSubscribedEventsItem  # what an endpoint can subscribe to

# ── storage ────────────────────────────────────────────────────────────
StorageConnection = GetStorageResponseData
StorageCreate = CreateStorageRequestParams  # storage.create(): one dict per provider, by `provider`
StorageCredentials = UpdateStorageRequestCredentialsParams  # storage.update(credentials=...)
StorageConflict = UpdateStorageRequestOnConflict
StorageTestResult = TestStorageResponseData
StorageActivity = GetStorageStatsResponseData
StorageObjects = ListStorageObjectsResponseData
PreparedAwsStorage = PrepareAwsStorageResponseData
AwsAccess = PrepareAwsStorageRequestAccess
AccountBuckets = ListAccountBucketsResponseData
BucketProvider = ListAccountBucketsRequestProvider
S3BucketLookup = LookUpS3BucketResponseData
SupabaseSignIn = StartSupabaseStorageResponseData
SupabaseProjects = GetSupabaseSessionResponseData
SupabaseBuckets = ListSupabaseBucketsResponseData

# ── API keys ───────────────────────────────────────────────────────────
CreatedApiKey = CreateApiKeyResponseData  # an ApiKey plus `key`, the secret, shown only here
ApiKeyRevoked = RevokeApiKeyResponseData

# ── organizations ──────────────────────────────────────────────────────
OrgMembership = ListOrgsResponseDataItem  # an organization you belong to, with your `role`
CurrentOrg = GetCurrentOrgResponseData
NewOrganization = CreateOrgResponseData
Organization = UpdateOrgResponseData
OrgSettings = GetOrgSettingsResponseData
Region = UpdateOrgSettingsRequestDefaultRegion
Invitation = InviteOrgMemberResponseData
InviteRole = InviteOrgMemberRequestRole  # orgs.members.invite(role=...)
MemberRole = UpdateOrgMemberRoleRequestRole  # orgs.members.change_role(role=...)
MemberRoleChanged = UpdateOrgMemberRoleResponseData
MemberRemoved = RemoveOrgMemberResponseData
InvitationRevoked = RevokeOrgInvitationResponseData

# ── compose ────────────────────────────────────────────────────────────
ComposeEffects = ListComposeEffectsResponseData
ComposeEngineEffects = ListComposeEngineEffectsResponseData
# What compose.validate() returns. Branch on `valid` or isinstance: a ComposeValid carries the params
# as a render reads them and the `price`; a ComposeInvalid carries the `problems`.
ComposeValid = ValidateComposeResponseDataPrice
ComposeInvalid = ValidateComposeResponseDataProblems
ComposeValidation = Union[ComposeValid, ComposeInvalid]

# ── notifications ──────────────────────────────────────────────────────
Notification = ListNotificationsResponseDataItem
NotificationsMeta = ListNotificationsResponseMeta
NotificationsRead = MarkNotificationsReadResponseData

# The models whose generated name is not their public one.
RESOURCE_MODELS: Dict[str, Type[object]] = {
    "OffsetPageMeta": OffsetPageMeta,
    "ListMeta": ListMeta,
    "DeliveriesPageMeta": DeliveriesPageMeta,
    "JobLogEntry": JobLogEntry,
    "JobTimings": JobTimings,
    "JobStats": JobStats,
    "DeliveriesRetried": DeliveriesRetried,
    "BillingState": BillingState,
    "UsageSummary": UsageSummary,
    "ClientUsage": ClientUsage,
    "Transaction": Transaction,
    "Invoice": Invoice,
    "CreditsCheckout": CreditsCheckout,
    "PlanCheckoutStarted": PlanCheckoutStarted,
    "PlanChanged": PlanChanged,
    "Subscription": Subscription,
    "PaymentMethod": PaymentMethod,
    "DefaultPaymentMethod": DefaultPaymentMethod,
    "BillingPortal": BillingPortal,
    "Asset": Asset,
    "AssetDownload": AssetDownload,
    "AssetDeleted": AssetDeleted,
    "WebhookEndpointWithSecret": WebhookEndpointWithSecret,
    "WebhookTestResult": WebhookTestResult,
    "WebhookDelivery": WebhookDelivery,
    "RetriedDelivery": RetriedDelivery,
    "StorageConnection": StorageConnection,
    "StorageTestResult": StorageTestResult,
    "StorageActivity": StorageActivity,
    "StorageObjects": StorageObjects,
    "PreparedAwsStorage": PreparedAwsStorage,
    "AccountBuckets": AccountBuckets,
    "S3BucketLookup": S3BucketLookup,
    "SupabaseSignIn": SupabaseSignIn,
    "SupabaseProjects": SupabaseProjects,
    "SupabaseBuckets": SupabaseBuckets,
    "CreatedApiKey": CreatedApiKey,
    "ApiKeyRevoked": ApiKeyRevoked,
    "OrgMembership": OrgMembership,
    "CurrentOrg": CurrentOrg,
    "NewOrganization": NewOrganization,
    "Organization": Organization,
    "OrgSettings": OrgSettings,
    "Invitation": Invitation,
    "MemberRoleChanged": MemberRoleChanged,
    "MemberRemoved": MemberRemoved,
    "InvitationRevoked": InvitationRevoked,
    "ComposeEffects": ComposeEffects,
    "ComposeEngineEffects": ComposeEngineEffects,
    "ComposeValid": ComposeValid,
    "ComposeInvalid": ComposeInvalid,
    "Notification": Notification,
    "NotificationsMeta": NotificationsMeta,
    "NotificationsRead": NotificationsRead,
}

publish(RESOURCE_MODELS)

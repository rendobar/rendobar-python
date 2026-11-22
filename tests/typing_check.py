"""What a type checker sees in a user's code. CI runs pyright (strict) and mypy --strict on it; nothing runs it.

Each `assert_type` fails the check when a public type drifts, such as back to
`Any`. Each `type: ignore[...]` marks a line that must stay an error: both
checkers report an ignore that is no longer needed, so a submit mistake that
starts to type-check fails CI.
"""
# pyright: strict, reportUnnecessaryTypeIgnoreComment=true
from __future__ import annotations

from typing import AsyncIterator, Iterator, List, Optional, Union

from typing_extensions import assert_type

from rendobar import (
    AccountCapabilities,
    AsyncRendobar,
    ErrorCode,
    Job,
    JobCancellation,
    JobCancelled,
    JobComplete,
    JobCompletedOnSubmit,
    JobCost,
    JobCreated,
    JobFailed,
    JobFailedError,
    JobReplayed,
    JobType,
    JobTypeSchema,
    FfprobeResult,
    output_data,
    PageMeta,
    Problem,
    Rendobar,
    RendobarError,
    UnknownJob,
    UntypedJob,
    WaitTimeoutError,
)
from rendobar import (
    ApiKey,
    Asset,
    AssetDeleted,
    BillingState,
    ClientUsage,
    ComposeInvalid,
    ComposeValid,
    CreatedApiKey,
    CurrentOrg,
    Invoice,
    JobLogEntry,
    JobStats,
    JobTimings,
    ListMeta,
    Notification,
    NotificationsMeta,
    OffsetPageMeta,
    OrgMembership,
    OrgSettings,
    Page,
    PlanChanged,
    PlanCheckoutStarted,
    StorageConnection,
    Transaction,
    UsageSummary,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEndpointWithSecret,
    WebhookTestResult,
)
from rendobar.webhooks import JobCompletedWebhookEvent, UnknownWebhookEvent, WebhookEvent, parse

Finished = Union[JobComplete, JobFailed, JobCancelled, UnknownJob]
URL = "https://cdn.rendobar.com/assets/examples/sample.mp4"


def submits(rb: Rendobar) -> None:
    job = rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, idempotency_key="order-1", label="probe", timeout=60)
    assert_type(job, JobComplete)
    assert_type(job.id, str)
    assert_type(job.cost, Optional[JobCost])
    if job.cost is not None:
        assert_type(job.cost.amount, int)
    assert_type(output_data(job, FfprobeResult), FfprobeResult)
    assert_type(job.terminal, bool)
    rb.jobs.run({"type": "ffmpeg", "params": {"command": f"ffmpeg -i {URL} out.mp4"}})
    rb.jobs.run(UntypedJob("video.newthing", {"quality": "high"}))  # the one way to a type the SDK does not know

    # The four submit mistakes, and a submit option put inside the job, each fail the check.
    rb.jobs.run({"type": "ffprobe", "params": {"comand": URL}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {"command": 123}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffporbe", "params": {"command": URL}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {"command": URL}, "label": "x"})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, no_such_option=1)  # type: ignore[call-overload]
    rb.jobs.create({"type": "ffprobe", "params": {"command": URL}}, destinations="storage://x")  # type: ignore[arg-type]

    # Request enums are closed and inputs are typed: each of these fails the check too.
    rb.jobs.run({"type": "ffmpeg", "params": {"command": "ffmpeg -i x out.mp4", "compute": "tpu"}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffmpeg", "params": {"command": "ffmpeg -i x out.mp4", "compute": 7}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "compress.target", "params": {"effort": "max"}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "image.upscale", "params": {"model": "seedvr9"}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, callback={"url": "https://x", "events": ["job.teleported"]})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffprobe", "params": {"command": URL}, "inputs": {"source": 5}})  # type: ignore[call-overload]
    rb.jobs.run({"type": "ffmpeg", "params": {"command": "ffmpeg -i x out.mp4", "compute": "gpu"}, "inputs": {"clips": [URL, {"job": "job_1"}]}})
    UntypedJob("video.newthing", inputs={"source": 5})  # type: ignore[dict-item]

    # Free-form response values are `object`: read them only after narrowing.
    job.params["preset"].upper()  # type: ignore[attr-defined]
    job.output.data["format"]  # type: ignore[index]
    job.steps[0].meta["k"]  # type: ignore[index]  # meta may be None
    job.nonexistent_attribute  # type: ignore[attr-defined]


def results(rb: Rendobar) -> None:
    assert_type(rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, throw_on_failure=False), Finished)
    assert_type(rb.jobs.wait("job_1"), Finished)
    assert_type(rb.jobs.wait("job_1", throw_on_failure=True), JobComplete)

    created = rb.jobs.create({"type": "ffprobe", "params": {"command": URL}})
    assert_type(created, Union[JobCreated, JobCompletedOnSubmit, JobReplayed])
    assert_type(created.id, str)

    got = rb.jobs.get("job_1")
    assert_type(got, Union[Job, UnknownJob])
    if isinstance(got, JobComplete):
        assert_type(got.output.files[0].url, str)
    if isinstance(got, JobFailed):
        assert_type(got.error.code, str)

    rb.jobs.list(status="complete")
    page = rb.jobs.list()
    assert_type(page, Page[Union[Job, UnknownJob], PageMeta])
    assert_type(page.data, List[Union[Job, UnknownJob]])
    assert_type(page.meta, PageMeta)
    assert_type(page.meta.total, int)
    assert_type(rb.jobs.list_all(), Iterator[Union[Job, UnknownJob]])
    assert_type(rb.jobs.cancel("job_1"), Union[JobCancellation, UnknownJob])
    assert_type(rb.jobs.download("job_1", "out.mp4"), int)
    assert_type(rb.jobs.types(), List[JobType])
    assert_type(rb.jobs.schema("ffprobe"), JobTypeSchema)
    assert_type(rb.account.capabilities(), AccountCapabilities)
    assert_type(rb.account.capabilities().plan.slug, str)


def errors(rb: Rendobar) -> None:
    try:
        rb.jobs.run({"type": "ffprobe", "params": {"command": URL}})
    except JobFailedError as err:
        assert_type(err.job, Union[JobFailed, JobCancelled, UnknownJob])
    except WaitTimeoutError as err:
        assert_type(err.job, Union[Job, UnknownJob])
    except RendobarError as err:
        assert_type(err.code, Union[ErrorCode, str])
        assert_type(err.problems, List[Problem])
        assert_type(err.idempotency_key, Optional[str])


def webhooks(body: bytes, headers: dict[str, str], secret: str) -> None:
    event = parse(body, headers, secret)
    assert_type(event, WebhookEvent)
    if isinstance(event, JobCompletedWebhookEvent):
        assert_type(event.data.job_id, str)
        assert_type(event.data.output.files[0].url, str)
    elif isinstance(event, UnknownWebhookEvent):
        assert_type(event.raw, dict[str, object])


async def async_client(rb: AsyncRendobar) -> None:
    job = await rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, idempotency_key="order-1", timeout=60)
    assert_type(job, JobComplete)
    await rb.jobs.run({"type": "ffprobe", "params": {"comand": URL}})  # type: ignore[call-overload]
    assert_type(await rb.jobs.run({"type": "ffprobe", "params": {"command": URL}}, throw_on_failure=False), Finished)
    assert_type(await rb.jobs.wait("job_1"), Finished)
    assert_type(await rb.jobs.create({"type": "ffprobe", "params": {"command": URL}}), Union[JobCreated, JobCompletedOnSubmit, JobReplayed])
    assert_type(await rb.jobs.get("job_1"), Union[Job, UnknownJob])
    assert_type((await rb.jobs.list()).data, List[Union[Job, UnknownJob]])
    assert_type(rb.jobs.list_all(), AsyncIterator[Union[Job, UnknownJob]])
    assert_type(await rb.jobs.cancel("job_1"), Union[JobCancellation, UnknownJob])
    assert_type(await rb.jobs.download("job_1", "out.mp4"), int)
    assert_type(await rb.jobs.types(), List[JobType])
    assert_type(await rb.jobs.schema("ffprobe"), JobTypeSchema)
    assert_type(await rb.account.capabilities(), AccountCapabilities)


def resources(rb: Rendobar) -> None:
    assert_type(rb.jobs.logs("job_1"), List[JobLogEntry])
    assert_type(rb.jobs.get_timings("job_1"), JobTimings)
    assert_type(rb.jobs.stats(window="7d"), JobStats)
    rb.jobs.stats(window="1y")  # type: ignore[arg-type]
    rb.jobs.list(sort="duration", order="asc", client="python", from_=0, to=1)
    rb.jobs.list(sort="name")  # type: ignore[arg-type]

    assert_type(rb.billing.state(), BillingState)
    assert_type(rb.billing.state().usage.job_count, int)
    assert_type(rb.billing.usage(), UsageSummary)
    assert_type(rb.billing.usage_by_client(days=30), List[ClientUsage])
    assert_type(rb.billing.transactions(), Page[Transaction, PageMeta])
    assert_type(rb.billing.history(), Page[Invoice, PageMeta])
    assert_type(rb.billing.checkout_plan("pro"), Union[PlanCheckoutStarted, PlanChanged])
    rb.billing.checkout_plan("platinum")  # type: ignore[arg-type]
    rb.billing.checkout_credits(10, interval="year")  # type: ignore[arg-type]

    asset = rb.uploads.create("clip.mp4", content_type="video/mp4", on_progress=lambda p: print(p.loaded, p.total))
    assert_type(asset, Asset)
    rb.uploads.create(b"bytes", filename="a.bin")
    rb.uploads.create(42)  # type: ignore[arg-type]
    assert_type(rb.assets.list(kind="media", limit=10), Page[Asset, OffsetPageMeta])
    rb.assets.list(kind="hologram")  # type: ignore[arg-type]
    assert_type(rb.assets.delete(asset.id), AssetDeleted)

    created = rb.webhooks.create(name="hook", url="https://example.com/h", subscribed_events=["job.completed", "balance.low"])
    assert_type(created, WebhookEndpointWithSecret)
    assert_type(created.signing_secret, str)
    rb.webhooks.create(name="hook", url="https://example.com/h", subscribed_events=["job.teleported"])  # type: ignore[list-item]
    assert_type(rb.webhooks.list(), Page[WebhookEndpoint, ListMeta])
    assert_type(rb.webhooks.update(created.id, active=False), WebhookEndpoint)
    assert_type(rb.webhooks.test(created.id), WebhookTestResult)
    deliveries = rb.webhooks.list_deliveries(endpoint_id=created.id, status="failed")
    assert_type(deliveries.data, List[WebhookDelivery])
    assert_type(rb.webhooks.delete(created.id), None)

    connection = rb.storage.create({"provider": "s3", "id": "media", "bucket": "b",
                                    "credentials": {"type": "keys", "access_key_id": "AK", "secret_access_key": "SK"}})
    assert_type(connection, StorageConnection)
    rb.storage.create({"provider": "s3", "id": "media", "bucket": "b"})  # type: ignore[arg-type]
    assert_type(rb.storage.list().data, List[StorageConnection])

    assert_type(rb.api_keys.list(), List[ApiKey])
    assert_type(rb.api_keys.create(scopes=["jobs:read"]), CreatedApiKey)
    assert_type(rb.orgs.list(), List[OrgMembership])
    assert_type(rb.orgs.current(), CurrentOrg)
    assert_type(rb.orgs.update_settings(default_region="eu-central-1"), OrgSettings)
    rb.orgs.update_settings(default_region="mars-1")  # type: ignore[arg-type]
    rb.orgs.members.invite(email="a@example.com", role="superuser")  # type: ignore[arg-type]

    validation = rb.compose.validate({"width": 1280})
    assert_type(validation, Union[ComposeValid, ComposeInvalid])
    notifications = rb.notifications.list()
    assert_type(notifications, Page[Notification, NotificationsMeta])
    assert_type(notifications.meta.unread, int)


async def async_resources(rb: AsyncRendobar) -> None:
    assert_type(await rb.jobs.logs("job_1"), List[JobLogEntry])
    assert_type(await rb.billing.state(), BillingState)
    assert_type(await rb.uploads.create("clip.mp4"), Asset)
    assert_type(await rb.webhooks.create(name="h", url="https://x", subscribed_events=["job.failed"]), WebhookEndpointWithSecret)
    assert_type(await rb.storage.get("media"), StorageConnection)
    assert_type(await rb.orgs.get_settings(), OrgSettings)
    assert_type(await rb.compose.validate({}), Union[ComposeValid, ComposeInvalid])
    assert_type((await rb.notifications.list()).meta, NotificationsMeta)

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
    rb.jobs.list(status="done")  # type: ignore[arg-type]
    page = rb.jobs.list()
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

"""What pyright sees in a user's code. CI's type check reads this file; nothing runs it.

Each `assert_type` fails the check when a public method's return type drifts,
such as back to `Any`. Each `pyright: ignore` marks a line that must stay an
error: with `reportUnnecessaryTypeIgnoreComment` on, an ignore that is no longer
needed fails the check too, so a typo'd attribute can never type-check again.
"""
# pyright: reportUnnecessaryTypeIgnoreComment=true
from __future__ import annotations

from typing import AsyncIterator, Iterator, List, Union

from typing_extensions import assert_type

from rendobar import (
    AccountCapabilities,
    AsyncRendobar,
    Job,
    JobCancellation,
    JobCancelled,
    JobComplete,
    JobCreated,
    JobFailed,
    JobFailedError,
    JobReplayed,
    JobType,
    JobTypeSchema,
    PageMeta,
    Rendobar,
    UnknownJob,
)

Finished = Union[JobComplete, JobFailed, JobCancelled]


def sync_client(rb: Rendobar) -> None:
    job = rb.jobs.run("ffprobe", {"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"},
                      idempotency_key="order-1", label="probe", timeout=60, interval=1, on_progress=print)
    assert_type(job, JobComplete)
    assert_type(job.id, str)
    job.nonexistent_attribute  # pyright: ignore[reportAttributeAccessIssue]
    rb.jobs.run("ffprobe", {}, no_such_option=1)  # pyright: ignore[reportCallIssue]

    assert_type(rb.jobs.run("ffprobe", throw_on_failure=False), Finished)
    assert_type(rb.jobs.wait("job_1"), Finished)
    assert_type(rb.jobs.wait("job_1", throw_on_failure=True), JobComplete)

    created = rb.jobs.create("ffprobe", {"command": "https://x/a.mp4"})
    assert_type(created, Union[JobCreated, JobReplayed, UnknownJob])
    assert_type(created.id, str)

    got = rb.jobs.get("job_1")
    assert_type(got, Union[Job, UnknownJob])
    got.output  # pyright: ignore[reportAttributeAccessIssue]  (only JobComplete has it)
    if isinstance(got, JobComplete):
        assert_type(got.output.files[0].url, str)
    if isinstance(got, JobFailed):
        assert_type(got.error.code, str)

    page = rb.jobs.list()
    assert_type(page.data, List[Union[Job, UnknownJob]])
    assert_type(page.meta, PageMeta)
    assert_type(page.meta.total, int)
    assert_type(rb.jobs.list_all(), Iterator[Union[Job, UnknownJob]])
    assert_type(rb.jobs.cancel("job_1"), Union[JobCancellation, UnknownJob])
    assert_type(rb.jobs.download("job_1"), bytes)
    assert_type(rb.jobs.types(), List[JobType])
    assert_type(rb.jobs.schema("ffprobe"), JobTypeSchema)
    assert_type(rb.account.capabilities(), AccountCapabilities)
    assert_type(rb.account.capabilities().plan.slug, str)

    try:
        rb.jobs.run("ffprobe")
    except JobFailedError as err:
        assert_type(err.job, Union[JobFailed, JobCancelled])


async def async_client(rb: AsyncRendobar) -> None:
    job = await rb.jobs.run("ffprobe", {"command": "https://x/a.mp4"}, idempotency_key="order-1", timeout=60)
    assert_type(job, JobComplete)
    job.nonexistent_attribute  # pyright: ignore[reportAttributeAccessIssue]
    assert_type(await rb.jobs.run("ffprobe", throw_on_failure=False), Finished)
    assert_type(await rb.jobs.wait("job_1"), Finished)
    assert_type(await rb.jobs.create("ffprobe"), Union[JobCreated, JobReplayed, UnknownJob])
    assert_type(await rb.jobs.get("job_1"), Union[Job, UnknownJob])
    assert_type((await rb.jobs.list()).data, List[Union[Job, UnknownJob]])
    assert_type(rb.jobs.list_all(), AsyncIterator[Union[Job, UnknownJob]])
    assert_type(await rb.jobs.cancel("job_1"), Union[JobCancellation, UnknownJob])
    assert_type(await rb.jobs.types(), List[JobType])
    assert_type(await rb.jobs.schema("ffprobe"), JobTypeSchema)
    assert_type(await rb.account.capabilities(), AccountCapabilities)

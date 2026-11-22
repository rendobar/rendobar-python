"""Submit a batch of jobs the safe way, and handle every error the SDK raises.

    RENDOBAR_API_KEY=rb_... python main.py

Idempotency keys make a resubmit return the same job, and a key reused with a
different body is refused. Then it pages through jobs, times out a wait, cancels
a job, and triggers the errors a worker meets.
"""
from __future__ import annotations

import os
from itertools import islice
from typing import Callable, NoReturn, Type, TypeVar

from rendobar import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InsufficientCreditsError,
    InternalServerError,
    InvalidArgumentError,
    JobCancelled,
    JobComplete,
    JobFailedError,
    JobReplayed,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    Rendobar,
    RendobarError,
    ResponseValidationError,
    SubmitJob,
    UnknownJob,
    UntypedJob,
    WaitTimeoutError,
    generate_idempotency_key,
)

VIDEO_URL = "https://cdn.rendobar.com/assets/examples/sample.mp4"
API_URL = os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com")
MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"
BATCH_SIZE = 3

E = TypeVar("E", bound=RendobarError)


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def probe(url: str) -> SubmitJob:
    return {"type": "ffprobe", "params": {"command": url}}


def describe(err: RendobarError) -> str:
    """One line per kind of error. Subclasses come before the classes they extend."""
    if isinstance(err, WaitTimeoutError):
        return f"wait gave up on {err.job_id}, last status {err.last_status}; the job may still finish"
    if isinstance(err, JobFailedError):
        return f"job {err.job_id} ended {err.status} with {err.code}"
    if isinstance(err, InvalidArgumentError):
        return f"refused before sending: {err.message}"
    if isinstance(err, APITimeoutError):
        return "the request timed out; resubmit with the same idempotency key"
    if isinstance(err, APIConnectionError):
        return f"no response ({err.code}); resubmit with the same idempotency key"
    if isinstance(err, BadRequestError):
        problems = "; ".join(f"{'.'.join(map(str, p.path))}: {p.message}" for p in err.problems)
        return f"400 {err.code}: {problems or err.message}"
    if isinstance(err, AuthenticationError):
        return f"{err.status_code or 'local'} {err.code}: check RENDOBAR_API_KEY"
    if isinstance(err, InsufficientCreditsError):
        return "402: add credits"
    if isinstance(err, PermissionDeniedError):
        return f"403 {err.code}: this key or plan may not do that"
    if isinstance(err, NotFoundError):
        return f"404 {err.code}"
    if isinstance(err, ConflictError):
        return f"409 {err.code}: {err.details}"
    if isinstance(err, RateLimitError):
        return f"429: retry after {err.retry_after} s"
    if isinstance(err, InternalServerError):
        return f"{err.status_code}: quote request id {err.request_id} to support"
    if isinstance(err, ResponseValidationError):
        return f"a response this SDK version cannot read ({err.status_code})"
    return f"{err.code}: {err.message}"


def raised(kind: Type[E], call: Callable[[], object]) -> E:
    """Run `call`, which must raise `kind`. Any other error propagates and fails the example."""
    try:
        call()
    except kind as err:
        print(f"  {type(err).__name__}: {describe(err)}")
        return err
    fail(f"expected {kind.__name__}")


def submit_batch(rb: Rendobar) -> None:
    keys = [generate_idempotency_key() for _ in range(BATCH_SIZE)]
    jobs = [rb.jobs.create(probe(VIDEO_URL), idempotency_key=key, label="example batch") for key in keys]
    print(f"submitted {[job.id for job in jobs]}")
    if len({job.id for job in jobs}) != BATCH_SIZE:
        fail("each key should create its own job")

    again = rb.jobs.create(probe(VIDEO_URL), idempotency_key=keys[0], label="example batch")
    print(f"resubmitted with the first key: {type(again).__name__} {again.id}")
    if not isinstance(again, JobReplayed) or again.id != jobs[0].id:
        fail(f"expected the first job back, got {again!r}")

    print("same key, different body:")
    try:
        rb.jobs.create(probe(f"{VIDEO_URL}?v=2"), idempotency_key=keys[0])
    except ConflictError as conflict:
        print(f"  ConflictError: {describe(conflict)}")
        if conflict.status_code != 409 or conflict.code != "CONFLICT":
            fail(f"conflict {conflict.status_code} {conflict.code}")
    else:
        if not MOCK:
            fail("a reused key with a different body was accepted")
        print("SKIP (mock: this mock version does not compare a reused key's body)")

    for job in jobs:
        done = rb.jobs.wait(job.id, timeout=300)
        print(f"job {done.id}: {done.status}")
        if not isinstance(done, JobComplete):
            fail(f"job {done.id} ended {done.status}")


def page_through(rb: Rendobar) -> None:
    # Two jobs per request, so six jobs take three pages.
    seen = [job.id for job in islice(rb.jobs.list_all(page_size=2), 6)]
    print(f"paged: {seen}")
    if len(set(seen)) != 6:
        fail(f"expected 6 distinct jobs, got {seen}")


def timeout_and_cancel(rb: Rendobar) -> None:
    job = rb.jobs.create(probe(VIDEO_URL), force_async=True, label="example cancel")
    print(f"job {job.id} queued; waiting less than it needs:")
    timed_out = raised(WaitTimeoutError, lambda: rb.jobs.wait(job.id, timeout=0.001))
    if timed_out.job_id != job.id or timed_out.last_status in ("complete", "failed", "cancelled"):
        fail(f"timeout on {timed_out.job_id} with status {timed_out.last_status}")

    cancelled = rb.jobs.cancel(job.id)
    print(f"cancel: {cancelled.status}")
    if isinstance(cancelled, UnknownJob) or cancelled.status != "cancelled":
        fail(f"cancel returned {cancelled!r}")

    try:
        ended = rb.jobs.wait(job.id, timeout=60, throw_on_failure=True)
    except JobFailedError as err:
        print(f"  JobFailedError: {describe(err)}")
        if err.code != "JOB_CANCELLED" or not isinstance(err.job, JobCancelled):
            fail(f"expected JOB_CANCELLED, got {err.code}")
        return
    if MOCK:
        print(f"SKIP (mock: cancel does not change the job, it ends {ended.status})")
        return
    fail(f"a cancelled job ended {ended.status}")


def errors(rb: Rendobar) -> None:
    print("errors:")
    raised(InvalidArgumentError, lambda: rb.jobs.list(limit=0))
    missing = raised(NotFoundError, lambda: rb.jobs.get("job_404"))
    if missing.status_code != 404:
        fail(f"not found answered {missing.status_code}")
    try:
        rb.jobs.create(UntypedJob("no_such_type", {}))
    except BadRequestError as bad:
        print(f"  BadRequestError: {describe(bad)}")
        if bad.status_code != 400:
            fail(f"bad request answered {bad.status_code}")
    else:
        if not MOCK:
            fail("an unknown job type was accepted")
        print("SKIP (mock: this mock version accepts any job type)")

    with Rendobar(api_key="", base_url=API_URL) as keyless:
        no_key = raised(AuthenticationError, lambda: keyless.jobs.get("job_404"))
    if no_key.code != "MISSING_API_KEY" or no_key.status_code is not None:
        fail(f"missing key: {no_key.code}")
    if MOCK:
        print("SKIP (mock: accepts any key, so a wrong key is not a 401)")
    else:
        with Rendobar("rb_not_a_real_key", base_url=API_URL) as wrong_key:
            wrong = raised(AuthenticationError, lambda: wrong_key.jobs.get("job_404"))
        if wrong.status_code != 401:
            fail(f"wrong key answered {wrong.status_code}")

    # Nothing listens on port 9, so the connection is refused.
    with Rendobar(base_url="http://127.0.0.1:9", max_retries=0) as unreachable:
        raised(APIConnectionError, lambda: unreachable.jobs.get("job_404"))


def main() -> None:
    with Rendobar(base_url=API_URL, app="example-batch-worker") as rb:
        submit_batch(rb)
        page_through(rb)
        timeout_and_cancel(rb)
        errors(rb)


if __name__ == "__main__":
    main()

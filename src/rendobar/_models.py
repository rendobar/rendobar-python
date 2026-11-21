"""Public names for the models the client returns.

The generated core (`_generated`, Fern) names models after their place in the
spec: `Job_Complete`, `SubmitJobResponseDataUrl`,
`GetAccountCapabilitiesResponseDataLimits`. This module gives each model a user
meets a short public name and exports it from `rendobar`, so annotations read
`JobComplete` and `type(job).__name__` is "JobComplete".

The classes are the generated ones, not copies: the public name is an alias,
and `_publish` renames the class at import so `type()`, `repr()` and pickling
agree with it. Nothing under `_generated` is edited, so a regeneration keeps
the names. A regeneration that renames or drops one of these models fails the
import here, in CI, instead of shipping a silent change.

It also holds what a submit takes: `SubmitJob`, the generated per-type union
(see fern/derive_overrides.py), and `UntypedJob`, the one way to submit a job
type this SDK does not know yet.
"""
# pyright: strict
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, Literal, Mapping, Optional, Type, Union, get_args

from ._generated.account.types.get_account_capabilities_response_data import GetAccountCapabilitiesResponseData
from ._generated.account.types.get_account_capabilities_response_data_features import GetAccountCapabilitiesResponseDataFeatures
from ._generated.account.types.get_account_capabilities_response_data_limits import GetAccountCapabilitiesResponseDataLimits
from ._generated.account.types.get_account_capabilities_response_data_plan import GetAccountCapabilitiesResponseDataPlan
from ._generated.jobs.types.cancel_job_response_data import CancelJobResponseData
from ._generated.jobs.types.get_job_type_schema_response_data import GetJobTypeSchemaResponseData
from ._generated.jobs.types.get_job_type_schema_response_data_inputs import GetJobTypeSchemaResponseDataInputs
from ._generated.jobs.types.list_jobs_response_meta import ListJobsResponseMeta
from ._generated.jobs.types.submit_job_response_data_idempotent import SubmitJobResponseDataIdempotent
from ._generated.jobs.types.submit_job_response_data_url import SubmitJobResponseDataUrl
from ._generated.requests.submit_any_job_callback import SubmitAnyJobCallbackParams
from ._generated.requests.submit_typed_job import SubmitTypedJobParams
from ._generated.types.job import Job_Cancelled, Job_Complete, Job_Dispatched, Job_Failed, Job_Running, Job_Waiting
from ._generated.types.job_failed_error import JobFailedError as _GeneratedJobError
from ._generated.types.job_complete_output import JobCompleteOutput
from ._generated.types.job_type import JobType

# A job, by status. Narrow with isinstance (`isinstance(job, JobComplete)`) to read
# the fields only that status has: `output` on JobComplete, `error` on JobFailed.
JobWaiting = Job_Waiting
JobDispatched = Job_Dispatched
JobRunning = Job_Running
JobComplete = Job_Complete
JobFailed = Job_Failed
JobCancelled = Job_Cancelled
Job = Union[JobWaiting, JobDispatched, JobRunning, JobComplete, JobFailed, JobCancelled]
JobError = _GeneratedJobError  # `JobFailed.error`: code, message, retryable, failed_phase
JobOutput = JobCompleteOutput  # `JobComplete.output`: data, file, files, expires_at


JobStatus = Literal["waiting", "dispatched", "running", "complete", "failed", "cancelled"]  # every status this SDK knows
KNOWN_STATUSES = frozenset(get_args(JobStatus))


class UnknownJob:
    """A job whose status this SDK version does not know yet.

    Returned instead of raising, so code written today keeps working when the
    API adds a status. `raw` holds the job as the API sent it. `jobs.wait()`
    treats an unknown status as not finished, so a wait on one ends at its
    timeout with a WaitTimeoutError carrying the job.
    """

    def __init__(self, raw: Mapping[str, object]) -> None:
        self.raw: Dict[str, object] = dict(raw)
        self.id: str = str(raw.get("id", ""))
        self.status: str = str(raw.get("status", ""))
        kind = raw.get("type")
        self.type: Optional[str] = kind if isinstance(kind, str) else None

    def __repr__(self) -> str:
        return f"UnknownJob(id={self.id!r}, status={self.status!r})"


SomeJob = Union[Job, UnknownJob]  # what a call that reads jobs returns
FinishedJob = Union[JobComplete, JobFailed, JobCancelled]  # what jobs.wait() returns

# What jobs.create() returns: the job it created (`status` "waiting", or "complete"
# for a job that finished during the request), or a replay of the job an earlier
# submit with the same idempotency key created.
JobCreated = SubmitJobResponseDataUrl
JobReplayed = SubmitJobResponseDataIdempotent
JobCancellation = CancelJobResponseData  # what jobs.cancel() returns: `id` and `status`

# What jobs.create() and jobs.run() take: a job of a type this SDK knows, as a dict
# typed per job type (`{"type": "ffprobe", "params": {"command": url}}`), so a
# misspelt or missing param, a wrong value type or an unknown type fails the
# type check. Generated from the spec: a new job type arrives with the next
# regeneration.
SubmitJob = SubmitTypedJobParams
Callback = SubmitAnyJobCallbackParams  # the `callback=` of jobs.create(): url, headers, verify, events


def _no_entries() -> Mapping[str, object]:
    return {}


@dataclass(frozen=True)
class UntypedJob:
    """A job of a type this SDK does not know yet. The one way to submit one.

    For a job type the SDK knows, pass its typed dict instead: `UntypedJob`
    skips the type check, so the API is the first to see a mistake.

        rb.jobs.run(UntypedJob("video.newthing", {"quality": "high"}))
    """

    type: str
    params: Mapping[str, object] = field(default_factory=_no_entries)
    inputs: Mapping[str, object] = field(default_factory=_no_entries)


JobTypeSchema = GetJobTypeSchemaResponseData
JobTypeInputs = GetJobTypeSchemaResponseDataInputs
PageMeta = ListJobsResponseMeta

AccountCapabilities = GetAccountCapabilitiesResponseData
AccountPlan = GetAccountCapabilitiesResponseDataPlan
AccountLimits = GetAccountCapabilitiesResponseDataLimits
AccountFeatures = GetAccountCapabilitiesResponseDataFeatures

__all__ = [
    "Job", "JobWaiting", "JobDispatched", "JobRunning", "JobComplete", "JobFailed", "JobCancelled",
    "JobError", "JobOutput", "JobStatus", "KNOWN_STATUSES", "UnknownJob", "SomeJob", "FinishedJob",
    "SubmitJob", "UntypedJob", "Callback", "JobCreated", "JobReplayed", "JobCancellation",
    "JobType", "JobTypeSchema", "JobTypeInputs", "PageMeta",
    "AccountCapabilities", "AccountPlan", "AccountLimits", "AccountFeatures", "PUBLIC_MODELS",
]

PUBLIC_MODELS: Dict[str, Type[object]] = {
    "JobWaiting": JobWaiting,
    "JobDispatched": JobDispatched,
    "JobRunning": JobRunning,
    "JobComplete": JobComplete,
    "JobFailed": JobFailed,
    "JobCancelled": JobCancelled,
    "JobError": JobError,
    "JobOutput": JobOutput,
    "JobCreated": JobCreated,
    "JobReplayed": JobReplayed,
    "JobCancellation": JobCancellation,
    "JobType": JobType,
    "JobTypeSchema": JobTypeSchema,
    "JobTypeInputs": JobTypeInputs,
    "PageMeta": PageMeta,
    "AccountCapabilities": AccountCapabilities,
    "AccountPlan": AccountPlan,
    "AccountLimits": AccountLimits,
    "AccountFeatures": AccountFeatures,
}


def _publish(models: Dict[str, Type[object]]) -> None:
    """Gives each class its public name, and binds that name in the class's own module.

    Pickle finds a class by `__module__` and `__qualname__`, so the generated
    module must answer to the new name too. `__module__` stays as generated:
    pydantic and `typing.get_type_hints` resolve the models' annotations in
    that module's namespace.
    """
    for name, cls in models.items():
        module = sys.modules[cls.__module__]
        bound = getattr(module, name, cls)
        if bound is not cls:
            raise RuntimeError(f"{cls.__module__}.{name} is already a different object; pick another public name")
        cls.__name__ = name
        cls.__qualname__ = name
        setattr(module, name, cls)


_publish(PUBLIC_MODELS)

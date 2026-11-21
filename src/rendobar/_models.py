"""Public names for the models the client returns, and what a submit takes.

Most models the SDK returns are named components in the spec (`JobCost`,
`JobOutput`, `OutputFile`, `JobCreated`, `FfprobeResult`, ...), so their
generated classes already carry their public names and this module only
re-exports them.

A few are not: the generated core inlines the variants of a discriminated
union (`Job_Complete` for the job union's `complete` variant,
`WebhookPayload_JobCompleted` for the webhook union's) and names inline
response bodies after their place in the spec
(`GetAccountCapabilitiesResponseDataLimits`). Those get a public name here,
and `_publish` renames the class at import so `type()`, `repr()` and pickling
agree with it. Nothing under `_generated` is edited, so a regeneration keeps
the names, and one that renames or drops a model fails the import here, in CI.

Submits take `SubmitJob`, the generated per-type union (see
fern/derive_overrides.py), or `UntypedJob`, the one way to submit a job type
this SDK does not type: one newer than it, or compose, whose params stay
untyped on purpose.
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
from ._generated.requests.submit_any_job_callback import SubmitAnyJobCallbackParams
from ._generated.requests.submit_typed_job import SubmitTypedJobParams
from ._generated.types.callback_status import CallbackStatus
from ._generated.types.ffprobe_result import FfprobeResult
from ._generated.types.ffprobe_summary import FfprobeSummary
from ._generated.types.job import Job_Cancelled, Job_Complete, Job_Dispatched, Job_Failed, Job_Running, Job_Waiting
from ._generated.types.job_completed_on_submit import JobCompletedOnSubmit
from ._generated.types.job_cost import JobCost
from ._generated.types.job_created import JobCreated
from ._generated.types.job_delivery import JobDelivery
from ._generated.types.job_error import JobError
from ._generated.types.job_output import JobOutput
from ._generated.types.job_replayed import JobReplayed
from ._generated.types.job_step import JobStep
from ._generated.types.job_type import JobType
from ._generated.types.output_file import OutputFile

__all__ = [
    "Job", "JobWaiting", "JobDispatched", "JobRunning", "JobComplete", "JobFailed", "JobCancelled",
    "JobError", "JobOutput", "OutputFile", "JobCost", "JobStep", "JobDelivery", "CallbackStatus",
    "JobStatus", "KNOWN_STATUSES", "UnknownJob", "SomeJob", "FinishedJob",
    "SubmitJob", "UntypedJob", "Callback", "JobCreated", "JobCompletedOnSubmit", "JobReplayed", "Submitted",
    "JobCancellation", "JobType", "JobTypeSchema", "JobTypeInputs", "PageMeta",
    "AccountCapabilities", "AccountPlan", "AccountLimits", "AccountFeatures",
    "FfprobeResult", "FfprobeSummary", "PUBLIC_MODELS",
]

# A job, by status. Narrow with isinstance (`isinstance(job, JobComplete)`) to read
# the fields only that status has: `output` on JobComplete, `error` on JobFailed.
JobWaiting = Job_Waiting
JobDispatched = Job_Dispatched
JobRunning = Job_Running
JobComplete = Job_Complete
JobFailed = Job_Failed
JobCancelled = Job_Cancelled
Job = Union[JobWaiting, JobDispatched, JobRunning, JobComplete, JobFailed, JobCancelled]

JobStatus = Literal["waiting", "dispatched", "running", "complete", "failed", "cancelled"]  # every status this SDK knows
KNOWN_STATUSES = frozenset(get_args(JobStatus))


class UnknownJob:
    """A job whose status this SDK version does not know yet.

    Returned instead of raising, so code written today keeps working when the
    API adds a status. `raw` holds the job as the API sent it, and `terminal`
    says whether that status is a final one: `jobs.wait()` stops on a terminal
    UnknownJob and keeps polling one that is not.
    """

    def __init__(self, raw: Mapping[str, object]) -> None:
        self.raw: Dict[str, object] = dict(raw)
        self.id: str = str(raw.get("id", ""))
        self.status: str = str(raw.get("status", ""))
        kind = raw.get("type")
        self.type: Optional[str] = kind if isinstance(kind, str) else None
        self.terminal: bool = raw.get("terminal") is True

    def __repr__(self) -> str:
        return f"UnknownJob(id={self.id!r}, status={self.status!r}, terminal={self.terminal})"


SomeJob = Union[Job, UnknownJob]  # what a call that reads jobs returns
# What jobs.wait() returns: a job that ended. An UnknownJob here has a final status newer than this SDK.
FinishedJob = Union[JobComplete, JobFailed, JobCancelled, UnknownJob]

# What jobs.create() returns: the job it created, one that finished during the request,
# or a replay of the job an earlier submit with the same idempotency key created.
Submitted = Union[JobCreated, JobCompletedOnSubmit, JobReplayed]

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
    """A job of a type this SDK does not type. The one way to submit one.

    That is a job type newer than this SDK, or compose, whose params are
    validated by the API (`jobs.schema("compose")` describes them). For any
    other type, pass its typed dict instead: `UntypedJob` skips the type
    check, so the API is the first to see a mistake.

        rb.jobs.run(UntypedJob("compose", {"width": 1280, "height": 720, "tracks": [...]}))
    """

    type: str
    params: Mapping[str, object] = field(default_factory=_no_entries)
    inputs: Mapping[str, object] = field(default_factory=_no_entries)


JobCancellation = CancelJobResponseData  # what jobs.cancel() returns: `id` and `status`
JobTypeSchema = GetJobTypeSchemaResponseData
JobTypeInputs = GetJobTypeSchemaResponseDataInputs
PageMeta = ListJobsResponseMeta

AccountCapabilities = GetAccountCapabilitiesResponseData
AccountPlan = GetAccountCapabilitiesResponseDataPlan
AccountLimits = GetAccountCapabilitiesResponseDataLimits
AccountFeatures = GetAccountCapabilitiesResponseDataFeatures

# The models whose generated name is not their public one. Named components are not here.
PUBLIC_MODELS: Dict[str, Type[object]] = {
    "JobWaiting": JobWaiting,
    "JobDispatched": JobDispatched,
    "JobRunning": JobRunning,
    "JobComplete": JobComplete,
    "JobFailed": JobFailed,
    "JobCancelled": JobCancelled,
    "JobCancellation": JobCancellation,
    "JobTypeSchema": JobTypeSchema,
    "JobTypeInputs": JobTypeInputs,
    "PageMeta": PageMeta,
    "AccountCapabilities": AccountCapabilities,
    "AccountPlan": AccountPlan,
    "AccountLimits": AccountLimits,
    "AccountFeatures": AccountFeatures,
}


def publish(models: Mapping[str, Type[object]]) -> None:
    """Gives each class its public name, and binds that name in the class's own module.

    Pickle finds a class by `__module__` and `__qualname__`, so the generated
    module must answer to the new name too. `__module__` stays as generated:
    pydantic and `typing.get_type_hints` resolve the models' annotations in
    that module's namespace. A name already bound there to another object is a
    clash, raised at import.
    """
    for name, cls in models.items():
        module = sys.modules[cls.__module__]
        bound = getattr(module, name, cls)
        if bound is not cls:
            raise RuntimeError(f"{cls.__module__}.{name} is already a different object; pick another public name")
        cls.__name__ = name
        cls.__qualname__ = name
        setattr(module, name, cls)


publish(PUBLIC_MODELS)

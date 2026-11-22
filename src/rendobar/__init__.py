"""Rendobar Python SDK: media processing and AI generation API for Python.

    from rendobar import Rendobar
    rb = Rendobar()  # reads RENDOBAR_API_KEY
    job = rb.jobs.run({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}})
"""
# pyright: strict
from ._async_client import AsyncAccount, AsyncJobs, AsyncRendobar
from ._client import (
    Account,
    DeprecationNotice,
    DownloadTarget,
    Jobs,
    Page,
    ProgressCallback,
    Rendobar,
    RendobarDeprecationWarning,
    generate_idempotency_key,
    output_data,
)
from ._errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    ErrorCode,
    InsufficientCreditsError,
    InternalServerError,
    InvalidArgumentError,
    JobFailedError,
    NotFoundError,
    PermissionDeniedError,
    PlanName,
    Problem,
    RateLimitError,
    RendobarError,
    ResponseValidationError,
    WaitTimeoutError,
    WebhookSignatureError,
)
from ._models import (
    AccountCapabilities,
    AccountFeatures,
    AccountLimits,
    AccountPlan,
    Callback,
    CallbackStatus,
    FfprobeAudioSummary,
    FfprobeImageSummary,
    FfprobeOtherSummary,
    FfprobeResult,
    FfprobeSummary,
    FfprobeVideoSummary,
    FinishedJob,
    Job,
    JobCancellation,
    JobCancelled,
    JobComplete,
    JobCompletedOnSubmit,
    JobCost,
    JobCreated,
    JobDelivery,
    JobInput,
    JobDispatched,
    JobError,
    JobFailed,
    JobOutput,
    JobReplayed,
    JobRunning,
    JobStatus,
    JobStep,
    JobType,
    JobTypeInputs,
    JobTypeSchema,
    JobWaiting,
    OutputFile,
    PageMeta,
    SomeJob,
    SubmitJob,
    Submitted,
    UnknownJob,
    UntypedJob,
)
from ._version import __version__

__all__ = [
    # clients
    "Rendobar", "AsyncRendobar", "Jobs", "AsyncJobs", "Account", "AsyncAccount",
    "Page", "DeprecationNotice", "RendobarDeprecationWarning", "generate_idempotency_key",
    "DownloadTarget", "ProgressCallback",
    # submitting
    "SubmitJob", "UntypedJob", "Callback", "JobInput", "Submitted", "output_data",
    # jobs
    "Job", "SomeJob", "FinishedJob", "JobStatus", "UnknownJob",
    "JobWaiting", "JobDispatched", "JobRunning", "JobComplete", "JobFailed", "JobCancelled",
    "JobOutput", "OutputFile", "JobError", "JobCost", "JobStep", "JobDelivery", "CallbackStatus",
    "JobCreated", "JobCompletedOnSubmit", "JobReplayed", "JobCancellation",
    "FfprobeResult", "FfprobeSummary", "FfprobeVideoSummary", "FfprobeAudioSummary", "FfprobeImageSummary", "FfprobeOtherSummary",
    "JobType", "JobTypeSchema", "JobTypeInputs", "PageMeta",
    "AccountCapabilities", "AccountPlan", "AccountLimits", "AccountFeatures",
    # errors
    "RendobarError", "ErrorCode", "PlanName", "Problem",
    "BadRequestError", "AuthenticationError", "InsufficientCreditsError",
    "PermissionDeniedError", "NotFoundError", "ConflictError", "RateLimitError", "InternalServerError",
    "InvalidArgumentError", "APIConnectionError", "APITimeoutError", "ResponseValidationError",
    "JobFailedError", "WaitTimeoutError", "WebhookSignatureError",
    "__version__",
]

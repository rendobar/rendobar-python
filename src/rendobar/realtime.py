"""The events a workspace streams as they happen: job progress, logs and status, balance and notification changes.

Stream them with `rb.realtime.subscribe_job(job_id)` (one job, until it ends)
or `rb.realtime.connect()` (the whole workspace). Both need the optional
WebSocket dependency: ``pip install "rendobar[realtime]"``. This module, the
event types, imports without it.

    from rendobar import Rendobar, realtime

    with Rendobar() as rb:
        job = rb.jobs.create({"type": "ffprobe", "params": {"command": "https://example.com/a.mp4"}})
        for event in rb.realtime.subscribe_job(job.id):
            if isinstance(event, realtime.JobProgress):
                print(event.phase, event.progress)
            elif isinstance(event, realtime.JobStatusChanged):
                print("status", event.status)

Every event has `type` (its name on the wire) and `event_id`, the stream's
cursor (0 for an event the workspace does not keep for replay, such as
progress). A message this SDK cannot read, a type newer than it or a known
type whose fields changed shape, is an `UnknownRealtimeEvent`, never an error.
"""
# pyright: strict
from __future__ import annotations

import json
from typing import Dict, Literal, Optional, Tuple, Type, Union

import pydantic
from pydantic.alias_generators import to_camel

from ._errors import as_mapping
from ._models import JobStatus

__all__ = [
    "RealtimeEvent", "UnknownRealtimeEvent", "Connected", "ReplayDone", "Resync", "ResyncReason",
    "JobCreated", "JobStatusChanged", "JobResult", "JobRegionFailover", "JobProgress", "Phase", "JobStep",
    "JobLog", "LogLevel", "JobContext", "JobResources", "JobPreview", "BalanceUpdated", "SubscriptionUpdated",
    "ApiKeysUpdated", "StorageConnected", "StorageRemoved", "StorageProblem", "Notification",
    "NotificationSeverity", "OrgUpdated", "MemberUpdated", "LeaveReason", "WorkspaceRole",
]

# Open enums: the values this SDK knows, or any other string from a newer API.
Phase = Union[Literal["preparing", "processing", "finalizing"], str]
LogLevel = Union[Literal["debug", "info", "warn", "error"], str]
ResyncReason = Union[Literal["buffer_overflow", "server_restart"], str]
NotificationSeverity = Union[Literal["info", "success", "warning", "error"], str]
WorkspaceRole = Union[Literal["owner", "admin", "member"], str]
LeaveReason = Union[Literal["removed", "left"], str]  # another member removed them, or they left


class _Event(pydantic.BaseModel):
    """Fields in snake case, read from the API's camelCase. Fields this SDK does not know are kept (`model_extra`)."""

    model_config = pydantic.ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow", frozen=True)

    event_id: int = 0
    """The stream's cursor for this event, or 0 for one the workspace does not keep for replay.
    Pass the last one you handled as `connect(last_event_id=...)` to resume after it."""


class Connected(_Event):
    """Yielded each time the stream connects, the first time included. Replayed events follow, then `ReplayDone`."""

    type: Literal["connected"] = "connected"


class ReplayDone(_Event):
    """The replayed events are over: what follows is live."""

    type: Literal["replay.done"] = "replay.done"


class Resync(_Event):
    """The stream lost events it cannot replay. Read the state you show again, such as `jobs.list()`."""

    type: Literal["resync"] = "resync"
    reason: ResyncReason


class JobCreated(_Event):
    """A job the workspace submitted."""

    type: Literal["job.created"] = "job.created"
    job_id: str
    job_type: str
    status: Union[JobStatus, str, None] = None


class JobStatusChanged(_Event):
    """A job moving to another status. `final` is True once it ended: complete, failed or cancelled."""

    type: Literal["job.status"] = "job.status"
    job_id: str
    status: Union[JobStatus, str]
    error: Optional[str] = None  # the failure message, for a failed job
    price: Optional[int] = None  # what the job cost in nanodollars, once it ended
    price_formatted: Optional[str] = None

    @property
    def final(self) -> bool:
        return self.status in ("complete", "failed", "cancelled")


class JobResult(_Event):
    """A job's output is ready. `jobs.get()` reads it."""

    type: Literal["job.result"] = "job.result"
    job_id: str


class JobRegionFailover(_Event):
    """A job moved to another region to run."""

    type: Literal["job.region_failover"] = "job.region_failover"
    job_id: str
    from_region: str
    to_region: str
    timestamp: Optional[int] = None  # Unix ms


class JobProgress(_Event):
    """How far a running job is. Build a progress display on `phase` and `progress`.

    `progress` is the fraction done, 0 to 1, or None when it cannot be told. It
    does not shrink. `eta` is the seconds left and may grow. `step` is the
    internal step, which varies by job type. `metrics` are the job's own
    numbers or texts, such as `fps`.
    """

    type: Literal["job.progress"] = "job.progress"
    job_id: str
    step: str
    timestamp: Optional[int] = None
    progress: Optional[float] = None
    phase: Optional[Phase] = None  # None from a runner that predates phases
    step_progress: Optional[float] = None
    eta: Optional[float] = None
    metrics: Optional[Dict[str, Union[float, str]]] = None


class JobStep(_Event):
    """A job's internal step starting or ending. It varies by job type, so prefer `JobProgress` for a display."""

    type: Literal["job.step"] = "job.step"
    job_id: str
    step: str
    status: str
    step_name: Optional[str] = None
    index: Optional[int] = None
    total: Optional[int] = None
    duration_ms: Optional[float] = None
    timestamp: Optional[int] = None


class JobLog(_Event):
    """One log line of a running job. `jobs.logs()` reads them all later."""

    type: Literal["job.log"] = "job.log"
    job_id: str
    level: LogLevel
    message: str
    step: Optional[str] = None
    event: Optional[str] = None
    duration_ms: Optional[float] = None
    meta: Optional[Dict[str, object]] = None  # free-form detail
    timestamp: Optional[int] = None


class JobContext(_Event):
    """The machine a job runs on."""

    type: Literal["job.context"] = "job.context"
    job_id: str
    machine: str
    cpu: Optional[float] = None
    memory: Optional[float] = None
    region: Optional[str] = None
    timestamp: Optional[int] = None


class JobResources(_Event):
    """One sample of what a running job uses. A value the runner could not measure is None."""

    type: Literal["job.resources"] = "job.resources"
    job_id: str
    timestamp: int
    cpu_pct: Optional[float] = None
    cpu_cores: Optional[float] = None
    allocated_cores: Optional[float] = None
    mem_used_mb: Optional[float] = pydantic.Field(None, alias="memUsedMB")
    mem_limit_mb: Optional[float] = pydantic.Field(None, alias="memLimitMB")
    threads: Optional[float] = None
    cpu_throttled_pct: Optional[float] = None
    cpu_pressure_pct: Optional[float] = None
    mem_pressure_pct: Optional[float] = None
    io_pressure_pct: Optional[float] = None
    disk_used_mb: Optional[float] = pydantic.Field(None, alias="diskUsedMB")
    disk_r_mbps: Optional[float] = pydantic.Field(None, alias="diskRMBps")
    disk_w_mbps: Optional[float] = pydantic.Field(None, alias="diskWMBps")
    net_rx_mbps: Optional[float] = pydantic.Field(None, alias="netRxMBps")
    net_tx_mbps: Optional[float] = pydantic.Field(None, alias="netTxMBps")
    gpu_pct: Optional[float] = None
    gpu_mem_used_mb: Optional[float] = pydantic.Field(None, alias="gpuMemUsedMB")
    gpu_mem_total_mb: Optional[float] = pydantic.Field(None, alias="gpuMemTotalMB")
    gpu_temp_c: Optional[float] = pydantic.Field(None, alias="gpuTempC")
    gpu_power_w: Optional[float] = pydantic.Field(None, alias="gpuPowerW")
    gpu_enc_pct: Optional[float] = None
    gpu_dec_pct: Optional[float] = None
    gpu_mem_bw_pct: Optional[float] = None


class JobPreview(_Event):
    """A small frame of an image while it generates. Not replayed. A `seq` at or below the last you showed is stale.

    `data` is a base64 WebP image, about 256 px on its long edge.
    """

    type: Literal["job.preview"] = "job.preview"
    job_id: str
    seq: int
    data: str
    progress: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    timestamp: Optional[int] = None


class BalanceUpdated(_Event):
    """The workspace's balance changing. `balance` and `txn_amount` are nanodollars."""

    type: Literal["balance.updated"] = "balance.updated"
    balance: int
    txn_type: Optional[str] = None
    txn_amount: Optional[int] = None
    balance_formatted: Optional[str] = None
    timestamp: Optional[int] = None


class SubscriptionUpdated(_Event):
    """The workspace's plan subscription changing."""

    type: Literal["subscription.updated"] = "subscription.updated"
    plan_id: str
    status: str
    cancel_at_period_end: Optional[bool] = None
    timestamp: Optional[int] = None


class ApiKeysUpdated(_Event):
    """A key was created, changed or revoked. It carries no key: read `api_keys.list()` again."""

    type: Literal["apikeys.updated"] = "apikeys.updated"
    timestamp: Optional[int] = None


class StorageConnected(_Event):
    """A storage connection finished connecting, such as an AWS stack reporting in."""

    type: Literal["storage.connected"] = "storage.connected"
    id: str
    timestamp: Optional[int] = None


class StorageRemoved(_Event):
    """A storage connection went away, such as its AWS stack being deleted."""

    type: Literal["storage.removed"] = "storage.removed"
    id: str
    timestamp: Optional[int] = None


class StorageProblem(_Event):
    """A storage connection failed. `storage.get()` says why."""

    type: Literal["storage.problem"] = "storage.problem"
    id: str
    timestamp: Optional[int] = None


class Notification(_Event):
    """A notification for the workspace. `href` is a dashboard path it is about."""

    type: Literal["notification"] = "notification"
    severity: NotificationSeverity
    title: str
    message: str
    id: Optional[str] = None
    href: Optional[str] = None
    requires_ack: Optional[bool] = None


class OrgUpdated(_Event):
    """The workspace renamed or given another slug."""

    type: Literal["org.updated"] = "org.updated"
    name: str
    slug: str
    timestamp: Optional[int] = None


class MemberUpdated(_Event):
    """A member's role changing (`role`), or a member leaving (`role` None, and `reason` says why)."""

    type: Literal["member.updated"] = "member.updated"
    user_id: str
    role: Optional[WorkspaceRole]
    reason: Optional[LeaveReason] = None
    timestamp: Optional[int] = None


class UnknownRealtimeEvent(_Event):
    """A message this SDK cannot read: a type newer than it, or a known type whose fields changed shape.

    `type` is its name on the wire and `raw` the message as sent.
    """

    type: str
    raw: Dict[str, object]

    @property
    def job_id(self) -> Optional[str]:
        """The job it names, when it names one."""
        value = self.raw.get("jobId")
        return value if isinstance(value, str) else None


KnownRealtimeEvent = Union[
    Connected, ReplayDone, Resync, JobCreated, JobStatusChanged, JobResult, JobRegionFailover, JobProgress, JobStep,
    JobLog, JobContext, JobResources, JobPreview, BalanceUpdated, SubscriptionUpdated, ApiKeysUpdated,
    StorageConnected, StorageRemoved, StorageProblem, Notification, OrgUpdated, MemberUpdated,
]
# What a stream yields. Check with isinstance; anything this SDK cannot read is an UnknownRealtimeEvent.
RealtimeEvent = Union[KnownRealtimeEvent, UnknownRealtimeEvent]

_TYPES: Dict[str, Type[KnownRealtimeEvent]] = {
    cls.model_fields["type"].default: cls
    for cls in (ReplayDone, Resync, JobCreated, JobStatusChanged, JobResult, JobRegionFailover, JobProgress, JobStep,
                JobLog, JobContext, JobResources, JobPreview, BalanceUpdated, SubscriptionUpdated, ApiKeysUpdated,
                StorageConnected, StorageRemoved, StorageProblem, Notification, OrgUpdated, MemberUpdated)
}
_ALIASES = {"job.metrics": "job.resources"}  # the old name of job.resources, from runners that predate it


def _cursor(fields: Dict[str, object]) -> int:
    """Takes the replay cursor off the message. It rides in `eventId`. An older hub wrote it into a numeric `id`,
    which an event's own id (a string, such as a notification's) never is."""
    event_id = fields.pop("eventId", None)
    if isinstance(event_id, int) and not isinstance(event_id, bool) and event_id > 0:
        if isinstance(fields.get("id"), int):
            fields.pop("id")
        return event_id
    legacy = fields.get("id")
    if isinstance(legacy, int) and not isinstance(legacy, bool):
        fields.pop("id")
        return legacy if legacy > 0 else 0
    return 0


def decode(frame: str) -> Optional[Tuple[RealtimeEvent, int]]:
    """One text frame as an event and its cursor, or None for a frame that is not a JSON object with a string `type`."""
    try:
        decoded: object = json.loads(frame)
    except ValueError:
        return None
    message = as_mapping(decoded)
    name = message.get("type") if message is not None else None
    if message is None or not isinstance(name, str) or not name:
        return None
    raw: Dict[str, object] = dict(message)
    fields = dict(raw)
    event_id = _cursor(fields)
    name = _ALIASES.get(name, name)
    cls = _TYPES.get(name)
    if cls is not None:
        try:
            return cls.model_validate({**fields, "type": name, "eventId": event_id}), event_id
        except pydantic.ValidationError:
            pass
    return UnknownRealtimeEvent(type=str(message["type"]), event_id=event_id, raw=raw), event_id


def about_job(event: RealtimeEvent, job_id: str) -> bool:
    """Whether `event` concerns the job `job_id`. A job's stream also carries the workspace's other events."""
    if isinstance(event, Connected):
        return True
    named: object = getattr(event, "job_id", None)
    return named == job_id


def ends_job(event: RealtimeEvent, job_id: str) -> bool:
    return isinstance(event, JobStatusChanged) and event.job_id == job_id and event.final


"""The Rendobar agent tools, framework-neutral.

The same four tools as `@rendobar/agent-toolkit` and the Rendobar MCP server,
with the same behaviour, so an agent acts the same through any of them:

- ``list_job_types``: what Rendobar can do now, or one type's params schema.
- ``run_job``: run any job and return its result.
- ``get_job``: a job's status and, once complete, its output.
- ``probe_media``: a file's duration, format and streams.

Descriptions never list job types. ``list_job_types`` reads the live registry,
so a new job type reaches every agent with no release. Every failure comes back
as data (``{"error": {"code", "message"}}``): a raised exception would end the
agent's whole loop over one bad call.

A job is billed once it exists, so ``run_job`` and ``probe_media`` create first
and wait second. A failure while waiting comes back with the job's ``id`` and a
hint to call ``get_job``, never an invitation to run it again. Only a failure
before any job exists says the call can be retried, and then with the same
``idempotency_key``, so even a submit whose response was lost cannot become a
second job.

Each framework adapter (``rendobar.agents.langchain``, ``rendobar.agents.crewai``)
wraps these and adds nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .._client import Rendobar, SomeJob, UnknownJob, generate_idempotency_key
from .._errors import APIConnectionError, RendobarError, WaitTimeoutError
from .._models import JobComplete, JobFailed


class ListJobTypesInput(BaseModel):
    type: Optional[str] = Field(default=None, description="A job type from the list, to get its params schema")


class RunJobInput(BaseModel):
    type: str = Field(description="Job type, from list_job_types")
    params: Dict[str, Any] = Field(default_factory=dict, description="Params for this job type, per its schema")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="Named input files, as URLs")
    wait: bool = Field(default=True, description="Wait for the job to finish. False returns the created job at once")
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Reuse the key a failed run_job returned to retry it without creating a second job. Omit on a first call",
    )


class GetJobInput(BaseModel):
    id: str = Field(description="Job id, such as job_abc123")


class ProbeMediaInput(BaseModel):
    url: str = Field(description="Public or signed URL of the media file")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_schema: Type[BaseModel]
    run: Callable[..., Dict[str, Any]]


def _plain(value: Any) -> Any:
    """Generated models to plain JSON values, so any framework can serialise them."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def summarize(job: SomeJob) -> Dict[str, Any]:
    """What an agent needs from a job, and nothing it would have to wade through."""
    out: Dict[str, Any] = {"id": job.id, "type": job.type, "status": job.status}
    if isinstance(job, JobComplete):
        output = job.output
        out["url"] = output.file.url if output.file is not None else None  # the headline file only, never a guess from `files`
        out["files"] = [{"url": f.url, "type": str(f.type), "path": f.path, "size": f.size} for f in output.files]
        if output.data is not None:
            out["data"] = _plain(output.data)
    if isinstance(job, JobFailed):
        out["error"] = {"code": job.error.code, "message": job.error.message}
    if not isinstance(job, UnknownJob) and job.cost is not None:
        out["cost"] = job.cost.formatted
    return out


_GET_JOB_HINT = "Call get_job with this id."


def _error_of(e: BaseException) -> Dict[str, Any]:
    """`{"code", "message"}` plus `request_id` when the API sent one. The message never repeats the other two."""
    if isinstance(e, RendobarError):
        out: Dict[str, Any] = {"code": e.code, "message": e.message}
        if e.request_id:
            out["request_id"] = e.request_id
        return out
    return {"code": "REQUEST_FAILED", "message": str(e).rstrip(".") or type(e).__name__}


def _guarded(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Every kind of failure as data the model can act on, never a raised exception. For calls that create nothing."""
    try:
        return fn()
    except WaitTimeoutError as e:
        return {"id": e.job_id, "status": e.last_status, "error": _error_of(e), "hint": _GET_JOB_HINT}
    except Exception as e:  # noqa: BLE001 (a dropped connection must not end the agent's loop)
        error = _error_of(e)
        if isinstance(e, APIConnectionError) or not isinstance(e, RendobarError):
            error["message"] = f"{error['message'].rstrip('.')}. The call can be retried."
        return {"error": error}


def _refused(e: BaseException) -> bool:
    """The API (or the client, for a missing key) refused the submit: no job exists, and repeating it cannot help.

    A 429 is "later", not "wrong", and a 5xx or a lost connection may hide a created job.
    """
    if not isinstance(e, RendobarError) or isinstance(e, APIConnectionError):
        return False
    return e.status_code is None or (e.status_code < 500 and e.status_code != 429)


def _create_then_wait(rb: Rendobar, type: str, params: Dict[str, Any], inputs: Optional[Dict[str, Any]],
                      *, wait: bool, idempotency_key: Optional[str]) -> Dict[str, Any]:
    """Create the job, then (optionally) wait for it, reporting each phase's failure for what it is."""
    key = idempotency_key or generate_idempotency_key()
    try:
        created = rb.jobs.create(type, params, inputs, idempotency_key=key)
    except Exception as e:  # noqa: BLE001 (see the module docstring)
        error = _error_of(e)
        if _refused(e):  # nothing was created: fix the call
            return {"error": error}
        # A lost response may hide a created job: the same key makes the retry return it, not a second one.
        error["message"] = f"{error['message']}. The call can be retried with this idempotency_key."
        return {"error": error, "idempotency_key": key}
    if not wait:
        return {"id": created.id, "status": created.status}
    try:
        return summarize(rb.jobs.wait(created.id, throw_on_failure=False))
    except Exception as e:  # noqa: BLE001
        status = e.last_status if isinstance(e, WaitTimeoutError) else created.status
        return {"id": created.id, "status": status, "error": _error_of(e), "hint": _GET_JOB_HINT}


def tool_definitions(client: Optional[Rendobar] = None, *, app: str = "agents") -> List[ToolDefinition]:
    """The four tools, bound to `client` (default: a client reading RENDOBAR_API_KEY)."""
    rb = client if client is not None else Rendobar(app=app)

    def list_job_types(type: Optional[str] = None) -> Dict[str, Any]:
        def go() -> Dict[str, Any]:
            if type is None:
                return {"job_types": [{"type": t.type, "summary": t.summary, "use_cases": list(t.use_cases)} for t in rb.jobs.types()]}
            try:
                return _plain(rb.jobs.schema(type))
            except RendobarError as e:
                if e.status_code == 404:
                    return {"error": {"code": "NOT_FOUND", "message": f'Job type "{type}" is not live. Call list_job_types.'}}
                raise

        return _guarded(go)

    def run_job(type: str, params: Optional[Dict[str, Any]] = None, inputs: Optional[Dict[str, Any]] = None,
                wait: bool = True, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return _create_then_wait(rb, type, params or {}, inputs, wait=wait, idempotency_key=idempotency_key)

    def get_job(id: str) -> Dict[str, Any]:
        return _guarded(lambda: summarize(rb.jobs.get(id)))

    def probe_media(url: str) -> Dict[str, Any]:
        return _create_then_wait(rb, "ffprobe", {"command": url}, None, wait=True, idempotency_key=None)

    return [
        ToolDefinition(
            "list_job_types",
            "List what Rendobar can do right now: every live media job type (video, audio, image, captions, compose, AI generation) with its use cases. Pass `type` to get that type's full params schema. Call this before run_job.",
            ListJobTypesInput,
            list_job_types,
        ),
        ToolDefinition(
            "run_job",
            "Run a Rendobar media job and return its result: status, output URL, files and data. Waits until the job finishes unless `wait` is false. Get valid `type` values and params from list_job_types first. URLs in params or inputs must be public or signed. If the result has an `id`, the job exists and is billed: follow it with get_job, do not run it again.",
            RunJobInput,
            run_job,
        ),
        ToolDefinition(
            "get_job",
            "Get a Rendobar job's current status and, once complete, its output URL, files and data.",
            GetJobInput,
            get_job,
        ),
        ToolDefinition(
            "probe_media",
            "Inspect a media file by URL: duration, format, streams, codecs, resolution, frame rate. Runs as a short ffprobe job, billed like any other job.",
            ProbeMediaInput,
            probe_media,
        ),
    ]

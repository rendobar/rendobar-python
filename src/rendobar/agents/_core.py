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

Each framework adapter (``rendobar.agents.langchain``, ``rendobar.agents.crewai``)
wraps these and adds nothing else.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .._client import Rendobar
from .._errors import RendobarError, WaitTimeoutError


class ListJobTypesInput(BaseModel):
    type: Optional[str] = Field(default=None, description="A job type from the list, to get its params schema")


class RunJobInput(BaseModel):
    type: str = Field(description="Job type, from list_job_types")
    params: Dict[str, Any] = Field(default_factory=dict, description="Params for this job type, per its schema")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="Named input files, as URLs")
    wait: bool = Field(default=True, description="Wait for the job to finish. False returns the created job at once")


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


def summarize(job: Any) -> Dict[str, Any]:
    """What an agent needs from a job, and nothing it would have to wade through."""
    out: Dict[str, Any] = {"id": job.id, "type": getattr(job, "type", None), "status": job.status}
    if job.status == "complete":
        output = job.output
        out["url"] = output.file.url if output.file is not None else (output.files[0].url if output.files else None)
        out["files"] = [{"url": f.url, "type": str(f.type), "path": f.path, "size": f.size} for f in output.files]
        if output.data is not None:
            out["data"] = _plain(output.data)
    if job.status == "failed":
        out["error"] = {"code": job.error.code, "message": job.error.message}
    cost = getattr(job, "cost", None)
    if cost is not None:
        out["cost"] = cost.formatted
    return out


def _guarded(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Every kind of failure as data the model can act on, never a raised exception."""
    try:
        return fn()
    except WaitTimeoutError as e:
        return {"id": e.job_id, "status": e.last_status, "error": {"code": "WAIT_TIMEOUT", "message": f"{e} Call get_job with this id later."}}
    except RendobarError as e:
        return {"error": {"code": e.code, "message": str(e), "request_id": e.request_id}}
    except Exception as e:  # noqa: BLE001 (a dropped connection must not end the agent's loop)
        message = str(e).rstrip(".") or type(e).__name__
        return {"error": {"code": "REQUEST_FAILED", "message": f"{message}. The call can be retried."}}


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

    def run_job(type: str, params: Optional[Dict[str, Any]] = None, inputs: Optional[Dict[str, Any]] = None, wait: bool = True) -> Dict[str, Any]:
        def go() -> Dict[str, Any]:
            if not wait:
                created = rb.jobs.create(type, params or {}, inputs)
                return {"id": created.id, "status": created.status}
            return summarize(rb.jobs.run(type, params or {}, inputs, throw_on_failure=False))

        return _guarded(go)

    def get_job(id: str) -> Dict[str, Any]:
        return _guarded(lambda: summarize(rb.jobs.get(id)))

    def probe_media(url: str) -> Dict[str, Any]:
        return _guarded(lambda: summarize(rb.jobs.run("ffprobe", {"command": url}, throw_on_failure=False)))

    return [
        ToolDefinition(
            "list_job_types",
            "List what Rendobar can do right now: every live media job type (video, audio, image, captions, compose, AI generation) with its use cases. Pass `type` to get that type's full params schema. Call this before run_job.",
            ListJobTypesInput,
            list_job_types,
        ),
        ToolDefinition(
            "run_job",
            "Run a Rendobar media job and return its result: status, output URL, files and data. Waits until the job finishes unless `wait` is false. Get valid `type` values and params from list_job_types first. URLs in params or inputs must be public or signed.",
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

<p align="center">
  <a href="https://rendobar.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://cdn.rendobar.com/assets/brand/logo-mark.svg">
      <img alt="Rendobar" src="https://cdn.rendobar.com/assets/brand/logo-mark-black.svg" width="80">
    </picture>
  </a>
</p>

<h1 align="center">Rendobar Python SDK</h1>

<p align="center">
  <strong>Media processing and AI generation API for Python.</strong>
</p>

<p align="center">
  <a href="https://rendobar.com/integrations/python-sdk/">Guide</a> &nbsp;·&nbsp;
  <a href="https://rendobar.com/docs/quickstart">Quickstart</a> &nbsp;·&nbsp;
  <a href="https://pypi.org/project/rendobar/">PyPI</a> &nbsp;·&nbsp;
  <a href="https://discord.gg/kAGqjBzx8N">Discord</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/rendobar/"><img src="https://img.shields.io/pypi/v/rendobar?style=flat-square&color=059669" alt="PyPI version"></a>
  <a href="https://pypi.org/project/rendobar/"><img src="https://img.shields.io/pypi/pyversions/rendobar?style=flat-square&color=059669" alt="Python versions"></a>
  <a href="https://github.com/rendobar/rendobar-python/actions"><img src="https://img.shields.io/github/actions/workflow/status/rendobar/rendobar-python/ci.yml?style=flat-square" alt="CI"></a>
</p>

`rendobar` is the official Python client for [Rendobar](https://rendobar.com), a serverless media processing API. Submit a job, wait for it, and get back a hosted file. It has sync and asyncio clients with full types, retries rate limits, server errors and failed connections on its own, and never turns a retried submit into a second job.

## Install

```bash
pip install rendobar
```

Python 3.10 or newer.

## Quickstart

```python
from rendobar import Rendobar

with Rendobar() as rb:  # reads RENDOBAR_API_KEY, or pass Rendobar("rb_...")
    job = rb.jobs.run({
        "type": "ffmpeg",
        "params": {"command": "ffmpeg -i https://cdn.rendobar.com/assets/examples/sample.mp4 -vf scale=1280:-2 out.mp4"},
    })
print(job.output.files[0].url)
```

`jobs.run()` submits the job and waits for it. Use `jobs.create()` and `jobs.wait()` to do the two steps yourself, and `rb.jobs.types()` to list every live job type.

The job is a dict typed per job type. Pyright, mypy and your editor know each type's params, so a misspelt or missing param, a wrong value type or an unknown job type fails the type check before anything runs.

The `with` block closes the client's connections when it ends. A long-lived client (one per app) can skip it and call `rb.close()` at shutdown.

### asyncio

```python
import asyncio

from rendobar import AsyncRendobar


async def main() -> None:
    async with AsyncRendobar() as rb:
        job = await rb.jobs.run({"type": "ffprobe", "params": {"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"}})
        print(job.output.data)


asyncio.run(main())
```

`AsyncRendobar` takes the same arguments and has the same methods as `Rendobar`, awaited. `await rb.aclose()` does the same as the `async with` block for a client you keep open. A call on a closed client raises `RendobarError` with code `CLIENT_CLOSED`.

## Client options

```python
from rendobar import Rendobar

rb = Rendobar(
    api_key="rb_...",                  # default: the RENDOBAR_API_KEY environment variable
    base_url="https://api.rendobar.com",
    timeout=30.0,                      # seconds per HTTP request
    max_retries=2,                     # retries of a 429, a 5xx or a failed connection
    app="my-app",                      # sent in X-Rendobar-Client, so your jobs show where they came from
    on_deprecation=print,              # called once per deprecated endpoint, see Support policy
)
```

`base_url` points the client at another server, such as a staging deployment or a local mock: `Rendobar(base_url="https://api.staging.example.com")`.

With no key passed and no `RENDOBAR_API_KEY` set (or an empty one), the client still works for `jobs.types()` and `jobs.schema()`, which need no key. Every other call raises `AuthenticationError` with code `MISSING_API_KEY` before it sends anything. A key that does not start with `rb_` gets code `INVALID_API_KEY` the same way, and the client never sends it.

## Submitting a job

The first argument of `jobs.create()` and `jobs.run()` says what to run: `type`, `params` and, for job types that read files, `inputs`. Everything about how to run it is a keyword argument, listed under [Job options](#job-options). A submit option inside the job dict is a type error.

```python
from rendobar import Rendobar, UntypedJob

rb = Rendobar()
rb.jobs.create({"type": "ffprobe", "params": {"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"}}, label="probe")

# A job type newer than your installed SDK: UntypedJob is the one way to submit it.
# It skips the type check, so the API is the first to see a mistake.
rb.jobs.create(UntypedJob("captions.translate", {"language": "de"}))
```

`rb.jobs.schema(type)` describes a job type's params at run time. The typed dicts come from the API spec, so a new job type gets its own type in the next release of this SDK.

## Job options

`jobs.run()` takes every option of `jobs.create()` and `jobs.wait()`. All of them are keyword arguments except `job`.

| Option | Method | What it does |
|---|---|---|
| `job` | create, run | What to run: a job dict typed per job type, or an `UntypedJob`. See [Submitting a job](#submitting-a-job). |
| `idempotency_key` | create, run | Makes the submit safe to repeat. See [Retries and idempotency](#retries-and-idempotency). |
| `label` | create, run | A short name for the job, shown in the dashboard and returned as `job.label`. |
| `destinations` | create, run | Where to deliver the output, as a list of `storage://<id>[/<folder or path>]`. |
| `callback` | create, run | A URL Rendobar POSTs the job to when it ends: `{"url": ..., "headers": {...}, "verify": True}`. |
| `force_async` | create, run | Queue the job even when its type can finish during the request. |
| `timeout` | wait, run | Seconds to wait before `WaitTimeoutError`. Default described below. |
| `interval` | wait, run | Seconds before the second poll (default 2). Each later pause is 1.5 times longer. |
| `max_interval` | wait, run | The longest pause between polls, in seconds (default 10). |
| `on_progress` | wait, run | Called with the job after every poll. |
| `throw_on_failure` | wait, run | Raise `JobFailedError` when the job fails or is cancelled. Default `True` for `run()`, `False` for `wait()`, which then returns the failed job. |

`jobs.wait()` with no `timeout` allows five minutes. Once the job reports its own execution budget (your plan's per-job limit), the wait extends to that budget plus two minutes, counted from the poll that saw it, so a long job is not cut off while it runs. Pass `timeout=` for a fixed bound.

## Results

Every method returns a typed result, so your editor completes fields and your type checker flags a misspelled one.

| Call | Returns |
|---|---|
| `jobs.run()` | `JobComplete` (with `throw_on_failure=False`: `JobComplete`, `JobFailed` or `JobCancelled`) |
| `jobs.wait()` | `JobComplete`, `JobFailed` or `JobCancelled` (with `throw_on_failure=True`: `JobComplete`) |
| `jobs.create()` | `JobCreated`, or `JobReplayed` when the idempotency key was used before |
| `jobs.get()`, `jobs.list()`, `jobs.list_all()` | `Job`: one of `JobWaiting`, `JobDispatched`, `JobRunning`, `JobComplete`, `JobFailed`, `JobCancelled` |
| `jobs.cancel()` | `JobCancellation` (`id` and `status`) |
| `jobs.types()`, `jobs.schema()` | a list of `JobType`, a `JobTypeSchema` |
| `account.capabilities()` | `AccountCapabilities` (`plan`, `limits`, `features`) |

Only a `JobComplete` has `output`, and only a `JobFailed` has `error`. Check which one you have with `isinstance`:

```python
from rendobar import JobComplete, JobFailed, Rendobar

rb = Rendobar()
job = rb.jobs.get("job_abc123")
if isinstance(job, JobComplete):
    print(job.output.files[0].url)
elif isinstance(job, JobFailed):
    print(job.error.code, job.error.message)
```

These names are aliases of the models generated from the API spec. `isinstance()` and annotations work with them, and `type(job).__name__` and `repr(job)` use them. Your editor's hovers and pyright's messages show the generated class name instead, such as `Job_Complete` for `JobComplete`, `SubmitJobResponseDataUrl` for `JobCreated` and `CancelJobResponseData` for `JobCancellation`. Nested models, such as the items of `job.output.files`, have only their generated names.

`jobs.list()` takes `status` as one of the six job statuses (`JobStatus`), `limit` (1 or more) and `offset` (0 or more).

`job.cost` is `None` until billing settles, which can be a moment after the job completes. Its `amount` is in nanodollars (1 USD = 1,000,000,000), and `formatted` has the same amount as dollars, such as `"$0.0021"`:

```python
from rendobar import JobComplete, Rendobar

rb = Rendobar()
job = rb.jobs.get("job_abc123")
if isinstance(job, JobComplete) and job.cost is not None:
    print(job.cost.formatted)
```

`jobs.download(job_id, to)` streams a completed job's output file to a path or to a binary file you opened, and returns the bytes written. It never holds the file in memory. A connection that breaks mid-file raises at once rather than retrying, and a file the call created is removed.

A job whose status is newer than your installed SDK comes back as `UnknownJob` with `id`, `status` and `raw`, rather than raising. That holds for every call that returns jobs (`get`, `list`, `list_all`, `create`, `cancel`, `wait`): in a list, only the job with the new status is an `UnknownJob`, the rest of the page is typed as usual. `jobs.wait()` treats a status it does not know as not finished, so a wait on one ends at its timeout with a `WaitTimeoutError` that carries the job.

## Errors

```python
from rendobar import NotFoundError, Rendobar, RendobarError

rb = Rendobar()
try:
    rb.jobs.get("job_missing")
except NotFoundError as err:
    print(err.code)        # "NOT_FOUND"
except RendobarError as err:
    print(err.status_code, err.code, err.request_id)  # quote request_id to support
```

Everything the SDK raises is a `RendobarError` with a `code`:

| Error | When |
|---|---|
| `BadRequestError`, `AuthenticationError`, `InsufficientCreditsError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `InternalServerError` | the API answered 400, 401, 402, 403, 404, 409, 429 or 5xx. `status_code` and `request_id` are set |
| `AuthenticationError` with code `MISSING_API_KEY` or `INVALID_API_KEY` | the client has no API key, or one that does not start with `rb_`. Raised before any request, so `status_code` is `None` |
| `InvalidArgumentError` (also a `ValueError`) | an argument the SDK refuses before any request: a job id that is not one path segment (`"../x"`), `limit` below 1, a negative `offset`, an invalid `app` name |
| `APIConnectionError` | no response: the connection failed or dropped |
| `APITimeoutError` (an `APIConnectionError`) | the request took longer than the client's `timeout` |
| `ResponseValidationError` | a response this SDK version cannot read, such as a success body that is not JSON (`body` holds it) |
| `RendobarError` with code `CLIENT_CLOSED` | a call on a client after `close()` or `aclose()` |
| `JobFailedError` | `jobs.run()`, or `jobs.wait(throw_on_failure=True)`, saw the job fail or be cancelled. `code` is the job's own error code and `job` the job |
| `WaitTimeoutError` | `jobs.wait()` gave up. The job may still finish. `job_id`, `last_status` and `job` (the last job read) are set |
| `WebhookSignatureError` | `rendobar.webhooks.parse()` got a delivery that is not signed with your secret, or is stale |

`code` is one of the codes in `ErrorCode` or, from a newer API, any other string, so compare it with strings rather than matching every case.

A refusal that lists what is wrong has `problems`: each one's `path` (such as `("params", "command")`), `message` and, on a plan refusal, `upgrade_to` (the plan that allows it). `details` holds the same list, or a mapping of other facts such as the `jobId` of a conflict.

```python
from rendobar import BadRequestError, Rendobar

rb = Rendobar()
try:
    rb.jobs.create({"type": "ffmpeg", "params": {"command": "ffmpeg -i https://example.com/missing.mp4 out.mp4"}})
except BadRequestError as err:
    for problem in err.problems:
        print(".".join(map(str, problem.path)), problem.message)
```

## Retries and idempotency

Only 429, 500, 502, 503, 504 and a connection that could not be made are retried, twice by default (`max_retries`). The client honours `Retry-After` (seconds or an HTTP date) up to 60 seconds, and a longer one raises the error with `retry_after` set. Without one, it backs off exponentially from half a second, with jitter. A retry that would sleep past the end of a `jobs.wait()` raises instead. Everything else raises at once: a 409 conflict, a 501, any other 4xx, and a request that timed out after reaching the API.

Retrying a submit never creates a second job. With no `idempotency_key`, `jobs.create()` generates one for that call and sends it on every retry, so the API returns the job the first attempt created. Pass your own key, such as an order id, to make separate calls safe to repeat. A repeat with the same key and the same params returns the first job as a `JobReplayed`. A repeat with the same key and different params raises `ConflictError` (409, code `CONFLICT`). Keys never expire.

When a submit fails in a way that may still have created the job (no answer, a timeout, or a 429 or 5xx after the last retry), the error's `idempotency_key` holds the key that was sent. Submit again with it to get that job, not a second one. `generate_idempotency_key()` makes keys of the same kind for your own use.

## Webhooks

```python
import os
from typing import Mapping

from rendobar import WebhookSignatureError
from rendobar.webhooks import JobCompletedEvent, JobFailedEvent, parse


def handle_rendobar_webhook(raw_body: bytes, headers: Mapping[str, str]) -> int:
    try:
        event = parse(raw_body, headers, os.environ["RENDOBAR_WEBHOOK_SECRET"])
    except WebhookSignatureError:
        return 401
    if isinstance(event, JobCompletedEvent):
        print(event.data.job_id, [file.url for file in event.data.output.files])
    elif isinstance(event, JobFailedEvent):
        print(event.data.job_id, event.data.error.code)
    return 200  # acknowledge every genuine delivery, including events you do not handle
```

`parse()` checks the signature, then returns the event typed by its name: `JobCreatedEvent`, `JobStartedEvent`, `JobCompletedEvent`, `JobFailedEvent`, `JobCancelledEvent`, `JobDeliverySucceededEvent`, `JobDeliveryFailedEvent`, `JobDeliveriesSettledEvent`, `BalanceLowEvent`, `BalanceDepletedEvent` or `TestEvent`. An event, or an envelope version, that your SDK does not know comes back as `UnknownWebhookEvent` with the body in `raw`, never as an exception, so a new event cannot break your handler. `verify()` is the signature check alone, as a bool, if you read the body yourself.

Pass the raw body exactly as received. Parsing and re-serialising the JSON first changes the bytes, and the signature no longer matches. An empty secret never verifies, so read it with `os.environ["RENDOBAR_WEBHOOK_SECRET"]` and let a missing one fail at startup.

Rendobar signs each delivery with these headers:

| Header | Value |
|---|---|
| `X-Rendobar-Timestamp` | when Rendobar sent it, in Unix seconds |
| `X-Rendobar-Signature` | `sha256=` and the hex HMAC-SHA256 of `"<timestamp>.<raw body>"`, keyed with your webhook secret. A signature without the `sha256=` prefix does not verify |
| `X-Rendobar-Signature-Previous` | during a secret rotation, the same signature made with the previous secret |

`verify()` recomputes the signature and compares it in constant time. It accepts either signature header, so a receiver holding the old or the new secret verifies during a rotation. It rejects a timestamp more than 300 seconds from now (`tolerance_seconds`) and a blank secret. A per-job callback sent with `"verify": True` carries the same headers, signed with your callback signing secret.

## AI agents

Give an agent Rendobar's four tools (`list_job_types`, `run_job`, `get_job`, `probe_media`), the same ones as the Rendobar MCP server. Failures come back to the model as data (`{"error": {"code", "message", "request_id"}}`), so one bad call does not end the run. Once a job exists, a failure while waiting returns its `id` and tells the model to call `get_job`, so a dropped connection never leads to a second billed job.

```bash
pip install "rendobar[langchain]"
```

```python
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from rendobar.agents.langchain import rendobar_tools


def build_agent(model: BaseChatModel):  # model: any LangChain chat model
    return create_agent(model, tools=rendobar_tools())
```

```bash
pip install "rendobar[crewai]"
```

```python
from crewai import Agent
from rendobar.agents.crewai import rendobar_tools


def video_editor() -> Agent:
    return Agent(role="Video editor", goal="Cut and caption clips", backstory="Edits for social", tools=rendobar_tools())
```

With no argument, `rendobar_tools()` builds a client that reads `RENDOBAR_API_KEY` and talks to `https://api.rendobar.com`. Pass your own client to choose the key, the server or any other [client option](#client-options):

```python
from rendobar import Rendobar
from rendobar.agents.langchain import rendobar_tools

tools = rendobar_tools(Rendobar(api_key="rb_...", base_url="https://api.staging.example.com"))
```

The `crewai` extra installs CrewAI itself, which brings about 120 packages and takes a few minutes. The `langchain` extra installs LangChain and LangGraph.

Frameworks that speak MCP (the OpenAI Agents SDK, the Claude Agent SDK) can connect to `https://api.rendobar.com/mcp` with no package.

## Framework examples

[`examples/`](examples) has a FastAPI app and Django views that submit a job and verify Rendobar's webhook. CI runs both against the conformance mock.

## Let your AI assistant do it

Paste this one line into Claude, ChatGPT, or Cursor and the assistant reads the integration playbook and wires Rendobar into your codebase. Your API key stays in your env file, never in the chat.

```text
Add Rendobar to my app: read and follow https://rendobar.com/prompts/integrate.md
```

## Support policy

- Python 3.10 to 3.13, tested on each. A Python version is dropped only after its end of life.
- Semantic versioning. A breaking change ships only in a major release, after at least 12 months of deprecation notices.
- A deprecated endpoint is reported once per endpoint through `on_deprecation` or a `RendobarDeprecationWarning` (a `FutureWarning`, so Python shows it by default), with the day it was deprecated.

## License

MIT. Rendobar is a product of Craftobar LLC.

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
    job = rb.jobs.run(
        type="ffmpeg",
        params={"command": "ffmpeg -i https://cdn.rendobar.com/assets/examples/sample.mp4 -vf scale=1280:-2 out.mp4"},
    )
print(job.output.file.url)
```

`jobs.run()` submits the job and waits for it. Use `jobs.create()` and `jobs.wait()` to do the two steps yourself, and `rb.jobs.types()` to list every live job type.

The `with` block closes the client's connections when it ends. A long-lived client (one per app) can skip it and call `rb.close()` at shutdown.

`jobs.wait()` with no `timeout` allows five minutes. Once the job reports its own execution budget (your plan's per-job limit), the wait extends to that budget plus two minutes, counted from the poll that saw it, so a long job is not cut off while it runs. Pass `timeout=` for a fixed bound.

### asyncio

```python
from rendobar import AsyncRendobar

async with AsyncRendobar() as rb:
    job = await rb.jobs.run(type="ffprobe", params={"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"})
```

`await rb.aclose()` does the same as the `async with` block for a client you keep open.

## Errors

```python
from rendobar import NotFoundError, RendobarError

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
| `APIConnectionError` | no response: the connection failed or dropped |
| `APITimeoutError` (an `APIConnectionError`) | the request took longer than the client's `timeout` |
| `ResponseValidationError` | a response this SDK version cannot read (`body` holds it) |
| `JobFailedError` | `jobs.run()`, or `jobs.wait(throw_on_failure=True)`, saw the job fail or be cancelled. `code` is the job's own error code |
| `WaitTimeoutError` | `jobs.wait()` gave up. The job may still finish |

Only 429, 5xx and a connection that could not be made are retried, twice by default (`max_retries`), honouring `Retry-After` (up to 60 seconds, a longer one raises `RateLimitError` with `retry_after` set) and backing off exponentially otherwise. Everything else raises at once: a 409 conflict, any other 4xx, and a request that timed out after reaching the API.

Retrying a submit never creates a second job. With no `idempotency_key`, `jobs.create()` generates one for that call and sends it on every retry, so the API returns the job the first attempt created. Pass your own key, such as an order id, to make separate calls safe to repeat. Keys never expire.

A job whose status is newer than your installed SDK comes back as `UnknownJob` with `id`, `status` and `raw`, rather than raising. That holds for every call that returns jobs (`get`, `list`, `list_all`, `create`, `cancel`, `wait`): in a list, only the job with the new status is an `UnknownJob`, the rest of the page is typed as usual.

## Webhooks

```python
import os
from rendobar.webhooks import verify

def handle_rendobar_webhook(raw_body: bytes, headers: dict) -> int:
    if not verify(raw_body, headers, os.environ["RENDOBAR_WEBHOOK_SECRET"]):
        return 401
    # The body is genuine: parse it and act on the event.
    return 200
```

Pass the raw body exactly as received. It checks the signature, rejects deliveries older than 5 minutes, and accepts the previous secret during a rotation. An empty secret never verifies, so read it with `os.environ["RENDOBAR_WEBHOOK_SECRET"]` and let a missing one fail at startup. The job id is at `data.jobId` in the parsed body.

## AI agents

Give an agent Rendobar's four tools (`list_job_types`, `run_job`, `get_job`, `probe_media`), the same ones as the Rendobar MCP server. Failures come back to the model as data, so one bad call does not end the run. Once a job exists, a failure while waiting returns its `id` and tells the model to call `get_job`, so a dropped connection never leads to a second billed job.

```bash
pip install "rendobar[langchain]"   # or "rendobar[crewai]"
```

```python
from langchain.agents import create_agent
from rendobar.agents.langchain import rendobar_tools

agent = create_agent(model, tools=rendobar_tools())  # model: any LangChain chat model
```

```python
from crewai import Agent
from rendobar.agents.crewai import rendobar_tools

editor = Agent(role="Video editor", goal="Cut and caption clips", backstory="Edits for social", tools=rendobar_tools())
```

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

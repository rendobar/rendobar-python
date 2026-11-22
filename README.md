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
  <strong>The official Python client for Rendobar's media processing and AI generation API.</strong><br>
  <code>pip install rendobar</code>
</p>

<p align="center">
  <a href="https://rendobar.com/docs/sdk/python">Docs</a> &nbsp;·&nbsp;
  <a href="https://rendobar.com/integrations/python-sdk/">Guide</a> &nbsp;·&nbsp;
  <a href="https://api.rendobar.com/reference">API reference</a> &nbsp;·&nbsp;
  <a href="https://pypi.org/project/rendobar/">PyPI</a> &nbsp;·&nbsp;
  <a href="https://app.rendobar.com">Get an API key</a> &nbsp;·&nbsp;
  <a href="https://discord.com/invite/kAGqjBzx8N">Discord</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/rendobar/"><img src="https://img.shields.io/pypi/v/rendobar?style=flat-square&color=059669" alt="PyPI version"></a>
  <a href="https://pypi.org/project/rendobar/"><img src="https://img.shields.io/pypi/pyversions/rendobar?style=flat-square&color=059669" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/rendobar?style=flat-square&color=059669" alt="License"></a>
</p>

The official Python client for Rendobar's media processing and AI generation API. With the `rendobar` package you submit a job, wait for it, and get back a hosted file URL. It has sync and asyncio clients with full types, retries rate limits, server errors and failed connections on its own, and never turns a retried submit into a second job.

It covers the same resources as `@rendobar/sdk`: jobs, uploads and assets, webhook endpoints, connected storage, API keys, organizations, billing, compose, notifications, the account and realtime events. See [What the client covers](#what-the-client-covers).

## Install

```bash
pip install rendobar
```

Python 3.10 or newer. For [realtime events](#realtime-events), install the `realtime` extra: `pip install "rendobar[realtime]"`.

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

## Let your AI assistant do it

Paste this one line into Claude, ChatGPT, or Cursor and the assistant reads the integration playbook and wires Rendobar into your codebase. Your API key stays in your env file, never in the chat.

```text
Add Rendobar to my app: read and follow https://rendobar.com/prompts/integrate.md
```

## Submitting a job

The first argument of `jobs.create()` and `jobs.run()` says what to run: `type`, `params` and, for job types that read files, `inputs`. Everything about how to run it is a keyword argument, listed under [Job options](#job-options). A submit option inside the job dict is a type error. Enum params are closed sets, so a value the job type does not take (`"compute": "tpu"`) fails the check too.

Each input is a URL, `{"url": ...}`, `{"content": ...}` for inline text such as subtitles, `{"job": "job_..."}` for another job's output, or a list of those for an input that takes several, such as the `images` of `image.edit` (`JobInput`).

A job dict written inline is checked where you pass it. One built in a variable first needs the annotation, or the checker infers a plain `dict`: `job: SubmitJob = {"type": "ffprobe", "params": {"command": url}}`.

```python
from rendobar import Rendobar, UntypedJob

rb = Rendobar()
rb.jobs.create({"type": "ffprobe", "params": {"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"}}, label="probe")

# A job type newer than your SDK version: UntypedJob is the one way to submit it.
# It skips the type check, so the API is the first to see a mistake.
rb.jobs.create(UntypedJob("your.new_job_type", {"option": "value"}))
```

`"your.new_job_type"` is a placeholder. It stands for a job type newer than your SDK version, one that `rb.jobs.types()` lists and the SDK has no typed dict for yet.

`UntypedJob` covers two cases: a job type newer than your installed SDK, and `compose`. Compose params nest timelines, tracks and effects that the spec does not name one by one, so the SDK leaves them untyped rather than ship generated names that change with every spec revision. `rb.jobs.schema("compose")` describes them, and the API validates every compose submit.

`rb.jobs.schema(type)` describes any job type's params at run time. The typed dicts come from the API spec, so a new job type gets its own type in the next release of this SDK.

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
| `jobs.wait()` | `JobComplete`, `JobFailed`, `JobCancelled`, or an `UnknownJob` that ended with a status newer than the SDK (with `throw_on_failure=True`: `JobComplete`) |
| `jobs.create()` | `JobCreated`, `JobCompletedOnSubmit` for a job that finished during the request, or `JobReplayed` when the idempotency key was used before |
| `jobs.get()`, `jobs.list()`, `jobs.list_all()` | `Job`: one of `JobWaiting`, `JobDispatched`, `JobRunning`, `JobComplete`, `JobFailed`, `JobCancelled`, or an `UnknownJob` for a status newer than the SDK |
| `jobs.cancel()` | `JobCancellation` (`id` and `status`) |
| `jobs.types()`, `jobs.schema()` | a list of `JobType`, a `JobTypeSchema` |
| `jobs.logs()`, `jobs.get_timings()`, `jobs.stats()` | a list of `JobLogEntry`, `JobTimings`, `JobStats` |
| `account.capabilities()` | `AccountCapabilities` (`plan`, `limits`, `features`) |
| any other resource | the model its method names, such as `Asset`, `WebhookEndpoint`, `StorageConnection`, `OrgSettings` or `BillingState`. One resource is one class, whichever method returned it |

A response field the SDK does not know is kept in `model_extra`, and an enum value newer than your SDK (a new delivery status, a new storage check) arrives as a plain string, so a newer API never breaks a parse. Enums you pass are closed sets: a value the API does not take fails the type check.

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

The models are generated from the API spec. Most are named components there, such as `JobCreated`, `JobCost`, `JobOutput`, `OutputFile`, `JobStep`, `JobDelivery`, `JobError` and `FfprobeResult`, and your editor shows those names. The six job variants are the exception: the generator inlines them into the `Job` union. `isinstance()`, annotations, `type(job).__name__` and `repr(job)` use their public names, but hovers and pyright's messages show the generated one, such as `Job_Complete` for `JobComplete`.

Counts, bytes, nanodollars and Unix-millisecond timestamps are `int`.

A job type with a typed result reads it with `output_data()`. Today that is ffprobe, with `FfprobeResult`:

```python
from rendobar import FfprobeResult, Rendobar, output_data

rb = Rendobar()
probe = rb.jobs.run({"type": "ffprobe", "params": {"command": "https://cdn.rendobar.com/assets/examples/sample.mp4"}})
result = output_data(probe, FfprobeResult)
if result.summary is not None:
    print(result.summary)
```

`result.summary` is one of `FfprobeVideoSummary`, `FfprobeAudioSummary`, `FfprobeImageSummary` or `FfprobeOtherSummary`, by its `kind`. A kind newer than your SDK leaves `summary` as `None` and keeps the value in `result.model_extra["unknown_summary"]`, so the rest of the result stays typed. `output_data()` raises `ResponseValidationError` only when the data is not that shape at all. Each job type the spec gives a result type gets one the same way.

Free-form values the API does not describe, such as `job.params` and `job.output.data`, are typed `object`, so your type checker asks you to narrow them before use.

`jobs.list()` takes `status` as one of the six job statuses (`JobStatus`), `type`, `limit` (1 or more), `offset` (0 or more), `sort` (`"created"`, `"duration"`, `"cost"`), `order`, `client` (such as `"python"`) and `from_`/`to` (Unix milliseconds). `jobs.list_all()` takes the same filters.

`job.cost` is `None` until billing settles, which can be a moment after the job completes. Its `amount` is in nanodollars (1 USD = 1,000,000,000), and `formatted` has the same amount as dollars, such as `"$0.0021"`:

```python
from rendobar import JobComplete, Rendobar

rb = Rendobar()
job = rb.jobs.get("job_abc123")
if isinstance(job, JobComplete) and job.cost is not None:
    print(job.cost.formatted)
```

`jobs.download(job_id, to)` streams a completed job's output file to a path or to a binary file you opened, and returns the bytes written. It never holds the file in memory. A connection that breaks mid-file raises at once rather than retrying, and a file the call created is removed.

A job whose status is newer than your installed SDK comes back as `UnknownJob` with `id`, `status` and `raw`, rather than raising. That holds for every call that returns jobs (`get`, `list`, `list_all`, `create`, `cancel`, `wait`): in a list, only the job with the new status is an `UnknownJob`, the rest of the page is typed as usual. Every job says whether it has ended (`terminal`), so `jobs.wait()` also stops on a status it does not know when that job is terminal, and returns it as an `UnknownJob`. `jobs.run()` raises `JobFailedError` (code `JOB_ENDED`) for it, since only `JobComplete` counts as success. A status that is not terminal is polled until the timeout.

## What the client covers

Each resource is an attribute of the client, with the same names as `@rendobar/sdk` in snake case. `AsyncRendobar` has the same resources and methods, awaited.

| Resource | Methods |
|---|---|
| `jobs` | `create`, `run`, `wait`, `get`, `list`, `list_all`, `cancel`, `download`, `logs`, `get_timings`, `stats`, `retry_deliveries`, `types`, `schema` |
| `uploads` | `create` |
| `assets` | `list`, `get`, `delete`, `download`, `templates` |
| `webhooks` | `create`, `list`, `get`, `update`, `delete`, `rotate_secret`, `test`, `list_deliveries`, `retry_delivery` |
| `storage` | `create`, `list`, `get`, `update`, `delete`, `test`, `stats`, `list_objects`, `prepare_aws`, `list_account_buckets`, `look_up_s3_bucket`, `start_supabase`, `list_supabase_projects`, `list_supabase_buckets`, `finish_supabase` |
| `api_keys` | `create`, `list`, `revoke`, `update` |
| `orgs` | `list`, `current`, `create`, `update`, `delete`, `get_settings`, `update_settings`, `members.invite`, `members.change_role`, `members.remove`, `invitations.revoke` |
| `billing` | `state`, `usage`, `usage_by_client`, `transactions`, `history`, `checkout_credits`, `checkout_plan`, `cancel_subscription`, `reactivate_subscription`, `cancel_credit_schedule`, `payment_methods`, `delete_payment_method`, `set_default_payment_method`, `portal_url` |
| `compose` | `effects`, `engine_effects`, `validate` |
| `notifications` | `list`, `mark_read` |
| `account` | `capabilities` |
| `realtime` | `connect`, `subscribe_job` (the `realtime` extra, see [Realtime events](#realtime-events)) |

The first argument of a method is the id it acts on, when it has one. Everything else is a keyword argument, so a new option never breaks a call you wrote. An argument left out, or passed as `None`, is not sent.

A list comes back as a `Page`: iterate it, or read `data` (the items) and `meta` (the totals the API reports, such as `total`). A list the API does not page, such as `api_keys.list()`, is a plain list.

```python
from rendobar import Rendobar

rb = Rendobar()
page = rb.webhooks.list_deliveries(status="failed", limit=20)
print(page.meta.total, [delivery.event for delivery in page])
for key in rb.api_keys.list():
    print(key.prefix, key.scopes)
```

Billing amounts (`billing.state().balance.amount`, transactions, invoices) are US dollars, as the API sends them. Job costs are integer nanodollars (see [Results](#results)).

### Uploads and assets

`uploads.create()` sends a local file (a path, or bytes with a `filename`) straight to storage on presigned URLs and returns the ready `Asset`. A large file goes up in parts, in parallel, and a file on disk is streamed, never read into memory whole. A job reads the asset as `asset://<id>`:

```python
from rendobar import Rendobar


def trim(rb: Rendobar, path: str) -> str:
    asset = rb.uploads.create(path, content_type="video/mp4", on_progress=lambda p: print(p.loaded, "of", p.total))
    job = rb.jobs.run({
        "type": "ffmpeg",
        "inputs": {"clip.mp4": f"asset://{asset.id}"},
        "params": {"command": "ffmpeg -i clip.mp4 -t 5 out.mp4"},
    })
    rb.assets.delete(asset.id)
    return job.output.files[0].url
```

An upload is ephemeral unless you pass `persist=True`: it expires on its own after 24 hours. A PUT to storage that fails is tried three times, then raises `RendobarError` with code `UPLOAD_FAILED`.

### Webhook endpoints

`webhooks.create()` returns a `WebhookEndpointWithSecret`. Its `signing_secret` is in plaintext only there and in `rotate_secret()`, so store it then. `webhooks.test()` sends a `test` event and reports whether your URL answered with a 2xx. To read a delivery your server receives, use `rendobar.webhooks.parse()` ([Webhooks](#webhooks)).

```python
from rendobar import Rendobar

rb = Rendobar()
endpoint = rb.webhooks.create(name="prod", url="https://example.com/rendobar-webhook", subscribed_events=["job.completed", "job.failed"])
print(endpoint.signing_secret)  # put it in your server's RENDOBAR_WEBHOOK_SECRET
print(rb.webhooks.test(endpoint.id).delivered)
rb.webhooks.delete(endpoint.id)
```

Creating an API key needs the `keys:write` scope, which no API key holds. With an API key, `api_keys.create()` raises `PermissionDeniedError` with code `INSUFFICIENT_SCOPE`. An OAuth access token or a dashboard session can create one.

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

A refusal that lists what is wrong has `problems`: each one's `path` (such as `("command",)`), `message` and, on a plan refusal, `upgrade_to` (the plan that allows it). `details` holds the same list, or a mapping of other facts such as the `jobId` of a conflict.

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

Only 429, 500, 502, 503, 504 and a connection that could not be made are retried, twice by default (`max_retries`). A 5xx is retried only for a request that is safe to repeat: a read, a keyed job submit, a cancel. A write such as `webhooks.create()` or `billing.checkout_credits()` may have taken effect before the 5xx, so it raises at once rather than run twice. The client honours `Retry-After` (seconds or an HTTP date) up to 60 seconds, and a longer one raises the error with `retry_after` set. Without one, it backs off exponentially from half a second, with jitter. A retry that would sleep past the end of a `jobs.wait()` raises instead. Everything else raises at once: a 409 conflict, a 501, any other 4xx, and a request that timed out after reaching the API.

Retrying a submit never creates a second job. With no `idempotency_key`, `jobs.create()` generates one for that call and sends it on every retry, so the API returns the job the first attempt created. Pass your own key, such as an order id, to make separate calls safe to repeat. A repeat with the same key and the same params returns the first job as a `JobReplayed`. A repeat with the same key and different params raises `ConflictError` (409, code `CONFLICT`). Keys never expire.

When a submit fails in a way that may still have created the job (no answer, a timeout, or a 429 or 5xx after the last retry), the error's `idempotency_key` holds the key that was sent. Submit again with it to get that job, not a second one. `generate_idempotency_key()` makes keys of the same kind for your own use.

## Webhooks

```python
import os
from typing import Mapping

from rendobar import WebhookSignatureError
from rendobar.webhooks import JobCompletedWebhookEvent, JobFailedWebhookEvent, parse


def handle_rendobar_webhook(raw_body: bytes, headers: Mapping[str, str]) -> int:
    try:
        event = parse(raw_body, headers, os.environ["RENDOBAR_WEBHOOK_SECRET"])
    except WebhookSignatureError:
        return 401
    if isinstance(event, JobCompletedWebhookEvent):
        print(event.data.job_id, [file.url for file in event.data.output.files])
    elif isinstance(event, JobFailedWebhookEvent):
        print(event.data.job_id, event.data.error.code)
    return 200  # acknowledge every genuine delivery, including events you do not handle
```

`parse()` checks the signature, then returns the event typed by its name: `JobCreatedWebhookEvent`, `JobStartedWebhookEvent`, `JobCompletedWebhookEvent`, `JobFailedWebhookEvent`, `JobCancelledWebhookEvent`, `JobDeliverySucceededWebhookEvent`, `JobDeliveryFailedWebhookEvent`, `JobDeliveriesSettledWebhookEvent`, `BalanceLowWebhookEvent`, `BalanceDepletedWebhookEvent` or `TestWebhookEvent`. An event, or an envelope version, that your SDK does not know comes back as `UnknownWebhookEvent` with the body in `raw` and a `reason` (`unknown_event`, `unknown_version` or `invalid_payload`), never as an exception, so a new event cannot break your handler. `verify()` is the signature check alone, as a bool, if you read the body yourself.

Pass the raw body exactly as received. Parsing and re-serialising the JSON first changes the bytes, and the signature no longer matches. An empty secret never verifies, so read it with `os.environ["RENDOBAR_WEBHOOK_SECRET"]` and let a missing one fail at startup.

Rendobar signs each delivery with these headers:

| Header | Value |
|---|---|
| `X-Rendobar-Timestamp` | when Rendobar sent it, in Unix seconds |
| `X-Rendobar-Signature` | `sha256=` and the hex HMAC-SHA256 of `"<timestamp>.<raw body>"`, keyed with your webhook secret. A signature without the `sha256=` prefix does not verify |
| `X-Rendobar-Signature-Previous` | during a secret rotation, the same signature made with the previous secret |

`verify()` recomputes the signature and compares it in constant time. It accepts either signature header, so a receiver holding the old or the new secret verifies during a rotation. It rejects a timestamp more than 300 seconds from now (`tolerance_seconds`) and a blank secret. A per-job callback sent with `"verify": True` carries the same headers, signed with your callback signing secret.

## Realtime events

`rb.realtime` streams a workspace's events over a WebSocket as they happen. It needs the `realtime` extra:

```bash
pip install "rendobar[realtime]"
```

`subscribe_job()` follows one job and stops after its final status:

```python
from rendobar import Rendobar, realtime


def follow(rb: Rendobar, job_id: str) -> None:
    for event in rb.realtime.subscribe_job(job_id, timeout=600):
        if isinstance(event, realtime.JobProgress):
            print(event.phase, event.progress)  # progress is 0 to 1, or None when it cannot be told
        elif isinstance(event, realtime.JobLog):
            print(event.level, event.message)
        elif isinstance(event, realtime.JobStatusChanged):
            print("status", event.status, event.final)
        # anything else: another event, or realtime.UnknownRealtimeEvent for one newer than this SDK
```

It yields `realtime.Connected`, then the job's progress, steps, logs, resources, previews, status and result, replayed ones first. A job that already ended stops after its replayed status. A job the workspace does not have raises `NotFoundError`. With `timeout` (seconds), a job that has not ended by then raises `RendobarError` with code `WAIT_TIMEOUT`.

`connect()` streams every event of the workspace, such as `realtime.BalanceUpdated` and `realtime.Notification`, until you stop iterating. It yields `realtime.Connected` on each connection, the events the workspace kept, `realtime.ReplayDone`, then live events.

Both reconnect with backoff (1 second, growing to 30) and resume after the last event they yielded, so you never see one twice. To resume in a later process, store the `event_id` of the last event you handled and pass it as `connect(last_event_id=...)`. `realtime.Resync` says events were lost: read your state again. A message this SDK cannot read, a type newer than it or a known type whose fields changed shape, comes back as `realtime.UnknownRealtimeEvent` with the message in `raw`, never as an exception. A refusal no reconnect fixes, such as a revoked key (401) or one without the `jobs:read` scope (403), raises its error. The key travels in the `Authorization` header, never in the URL.

On `AsyncRendobar` the same methods return async generators: `async for event in rb.realtime.subscribe_job(job_id)`. To close a stream before it ends, break out of the loop and drop it, or wrap it in `contextlib.closing` (`contextlib.aclosing` for async) to close it at a known point.

Without the extra, both methods raise `ImportError` naming it. The rest of the SDK, and the event types in `rendobar.realtime`, work without it.

## AI agents

Give an agent Rendobar's four tools: `list_job_types`, `run_job`, `get_job` and `probe_media`. They match the Rendobar MCP server's tools, and `run_job` is the MCP server's `submit_job` followed by a wait. Failures come back to the model as data (`{"error": {"code", "message", "request_id"}}`), so one bad call does not end the run. Once a job exists, a failure while waiting returns its `id` and tells the model to call `get_job`, so a dropped connection never leads to a second billed job.

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

## Client options

```python
from rendobar import Rendobar

rb = Rendobar(
    api_key="rb_...",                  # default: the RENDOBAR_API_KEY environment variable
    base_url="https://api.rendobar.com",
    timeout=30.0,                      # seconds per HTTP request
    max_retries=2,                     # retries of a 429, a 5xx or a failed connection
    app="my-app",                      # sent in X-Rendobar-Client, so your jobs show where they came from
    on_deprecation=print,              # called once per deprecated endpoint, see Versioning and support
)
```

`base_url` points the client at another server, such as a staging deployment or a local mock: `Rendobar(base_url="https://api.staging.example.com")`.

With no key passed and no `RENDOBAR_API_KEY` set (or an empty one), the client still works for `jobs.types()` and `jobs.schema()`, which need no key. Every other call raises `AuthenticationError` with code `MISSING_API_KEY` before it sends anything. A key that does not start with `rb_` gets code `INVALID_API_KEY` the same way, and the client never sends it.

## Examples

[`examples/`](examples) has small projects that use the SDK end to end. CI runs all of them against the conformance mock.

- [`quickstart`](examples/quickstart): probe a public video and print its duration, resolution and codecs.
- [`upload-process-download`](examples/upload-process-download): upload a clip, trim it with ffmpeg and stream the output back to disk.
- [`batch-worker`](examples/batch-worker): submit with idempotency keys, read logs, page through jobs and handle each error.
- [`webhook-receiver`](examples/webhook-receiver): manage a real webhook endpoint and verify the deliveries it receives.
- [`account-admin`](examples/account-admin): read billing, usage, API keys, org settings and notifications.
- [`realtime-progress`](examples/realtime-progress): follow a job live over the event stream.
- [`fastapi_app.py`](examples/fastapi_app.py): a FastAPI app that submits a job and verifies Rendobar's webhook.
- [`django_views.py`](examples/django_views.py): the same submit and webhook as Django views.

## Other Rendobar SDKs

- TypeScript: [`@rendobar/sdk`](https://www.npmjs.com/package/@rendobar/sdk) on npm.
- Go: [`github.com/rendobar/rendobar-go`](https://pkg.go.dev/github.com/rendobar/rendobar-go) on pkg.go.dev.
- NestJS module: [`@rendobar/nestjs`](https://www.npmjs.com/package/@rendobar/nestjs) on npm.
- Agent toolkit: [`@rendobar/agent-toolkit`](https://www.npmjs.com/package/@rendobar/agent-toolkit) on npm, tools for the Vercel AI SDK, Mastra and LangChain.js.

## Versioning and support

- Semantic versioning. Before 1.0, a minor release may tighten types, so code that type-checked before can fail the check after it. The changelog says so when one does.
- A deprecation is announced before anything is removed. See [rendobar.com/docs/support/versioning](https://rendobar.com/docs/support/versioning) and the [changelog](https://rendobar.com/changelog/).
- Python 3.10 to 3.13, tested on each. A Python version is dropped only after its end of life.
- A deprecated endpoint is reported once per endpoint through `on_deprecation` or a `RendobarDeprecationWarning` (a `FutureWarning`, so Python shows it by default), with the day it was deprecated.

## License

MIT. See [LICENSE](LICENSE). Rendobar is a product of Craftobar LLC.

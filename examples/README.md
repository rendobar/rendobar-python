# Examples

Small projects that use the `rendobar` package the way your code would. Each
folder is a project of its own: copy it, `pip install rendobar`, set
`RENDOBAR_API_KEY`, and run `python main.py`.

| Project | What it does | SDK calls |
|---|---|---|
| [`quickstart`](quickstart) | Probes a public video and prints its duration, resolution and codecs | `jobs.run` (ffprobe), `output_data(job, FfprobeResult)` |
| [`upload-process-download`](upload-process-download) | Trims and scales a video with ffmpeg, then streams the output to disk | `jobs.create` with typed params, `jobs.wait`, `jobs.download` |
| [`batch-worker`](batch-worker) | Submits jobs with idempotency keys, resubmits one (same job back), reuses a key with a different body (409), pages through jobs, times out a wait, cancels a job, and triggers the errors a worker meets | `generate_idempotency_key`, `jobs.create`, `JobReplayed`, `jobs.list_all`, `jobs.wait`, `jobs.cancel`, every error class |
| [`webhook-receiver`](webhook-receiver) | An `http.server` receiver that verifies each delivery and handles it by its typed event, with a branch for events newer than the SDK | `rendobar.webhooks.parse`, the typed events, `UnknownWebhookEvent` |
| [`account-admin`](account-admin) | Reads the workspace's plan limits and features, lists job types, and reads one type's params | `account.capabilities`, `jobs.types`, `jobs.schema` |

`fastapi_app.py` and `django_views.py` show the same submit and webhook in
those frameworks (`tests/test_examples.py` runs them).

## What this SDK does not have yet

The examples use only what the SDK has, so some steps other Rendobar SDKs show
are left out here:

- Uploads and assets: `upload-process-download` takes a public URL instead of a local file, and has no asset list, get or delete.
- Webhook endpoint management (create, list, update, rotate the secret, test, deliveries): `webhook-receiver` checks the receiver with deliveries it signs itself, plus the shared test vectors.
- Job logs: `batch-worker` does not read them.
- Billing, API keys and organization settings: `account-admin` reads capabilities and job types only.
- Realtime progress: there is no realtime client, so there is no `realtime-progress` project.

## Running them all

`run.py` builds the wheel, installs it into a fresh virtual environment, then
for each project runs pyright (strict) and `mypy --strict`, and runs it. It
needs [uv](https://docs.astral.sh/uv/) and exits non-zero if any project fails.

Mock mode is the default. It needs the conformance mock from
[rendobar/openapi](https://github.com/rendobar/openapi) running, the same one
the tests use (`RENDOBAR_MOCK`, default `http://127.0.0.1:4100`):

```bash
python3 -I .openapi/conformance/mock_server.py fern/openapi.json 4100 requests.jsonl &
python examples/run.py --mode mock
```

The mock answers with data synthesized from the spec, so a few checks cannot
hold there. Those print `SKIP (mock: <why>)` and still run in live mode.

Live mode runs real jobs, about six small ones per run, and needs a key and a
URL. Point it at staging:

```bash
RENDOBAR_API_KEY=rb_... RENDOBAR_API_URL=https://<staging API> python examples/run.py --mode live
```

## In CI

- `ci.yml`, job `examples`: mock mode on every pull request and push to main.
- `examples-live.yml`: live mode on demand and every Monday at 06:00 UTC, with
  the secrets `RENDOBAR_STAGING_API_KEY` and `RENDOBAR_STAGING_API_URL`.
- `release.yml` calls `examples-live.yml` after a release is cut and before the
  package is published, so a release that breaks a live example does not reach PyPI.

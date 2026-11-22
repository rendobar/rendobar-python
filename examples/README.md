# Examples

Small projects that use the `rendobar` package the way your code would. Each
folder is a project of its own: copy it, `pip install rendobar`, set
`RENDOBAR_API_KEY`, and run `python main.py`.

| Project | What it does | SDK calls |
|---|---|---|
| [`quickstart`](quickstart) | Probes a public video and prints its duration, resolution and codecs | `jobs.run` (ffprobe), `output_data(job, FfprobeResult)` |
| [`upload-process-download`](upload-process-download) | Uploads `fixtures/clip.mp4`, trims and scales it with ffmpeg reading `asset://<id>`, streams the output to disk, then lists, reads and deletes the asset | `uploads.create`, `jobs.create` with typed params, `jobs.wait`, `jobs.download`, `assets.list`, `assets.get`, `assets.delete` |
| [`batch-worker`](batch-worker) | Submits jobs with idempotency keys, resubmits one (same job back), reuses a key with a different body (409), reads a job's logs, pages through jobs, times out a wait, cancels a job, and triggers the errors a worker meets | `generate_idempotency_key`, `jobs.create`, `JobReplayed`, `jobs.logs`, `jobs.list_all`, `jobs.wait`, `jobs.cancel`, every error class |
| [`webhook-receiver`](webhook-receiver) | Creates a webhook endpoint, reads, lists and updates it, sends it a test event, reads and retries that delivery, rotates its secret and deletes it. Then an `http.server` receiver verifies deliveries signed with that secret and handles each typed event, with a branch for events newer than the SDK | `webhooks.create`, `get`, `list`, `update`, `test`, `list_deliveries`, `retry_delivery`, `rotate_secret`, `delete`, `rendobar.webhooks.parse`, `UnknownWebhookEvent` |
| [`account-admin`](account-admin) | Reads the workspace, its plan limits, billing state, usage, transactions and invoices, lists API keys and tries to create one, flips an org setting and restores it, reads notifications, and reads one job type's params | `orgs.current`, `orgs.list`, `account.capabilities`, `billing.state`, `billing.usage`, `billing.usage_by_client`, `billing.transactions`, `billing.history`, `api_keys.list`, `api_keys.create`, `api_keys.revoke`, `orgs.get_settings`, `orgs.update_settings`, `notifications.list`, `notifications.mark_read`, `jobs.types`, `jobs.schema` |
| [`realtime-progress`](realtime-progress) | Uploads `fixtures/clip.mp4`, starts an ffmpeg job on it and prints the job's live events (progress, logs, steps, status) until it ends, with a branch for events newer than the SDK. Needs the `realtime` extra | `uploads.create`, `jobs.create`, `realtime.subscribe_job`, `jobs.get`, `UnknownRealtimeEvent` |

`fastapi_app.py` and `django_views.py` show the same submit and webhook in
those frameworks (`tests/test_examples.py` runs them).

Every project deletes what it created (the asset, the webhook endpoint, a new
API key) and restores the org setting it changed, also when a step fails.

## What the examples leave out

- Creating an API key needs the `keys:write` scope, which no API key holds. With an API key, `account-admin` prints a `SKIP` for that step. An OAuth access token runs it.
- Steps that spend money or change the workspace for good never run: checkout, subscription changes, payment methods, creating or deleting an organization, and member invites.

`fixtures/clip.mp4` is a 2 second, 320x240 test pattern with a tone, 18 KB:

```bash
ffmpeg -f lavfi -i testsrc=d=2:s=320x240:r=24 -f lavfi -i sine=d=2 -shortest \
  -c:v libx264 -preset veryslow -crf 30 -pix_fmt yuv420p -c:a aac -b:a 32k -movflags +faststart clip.mp4
```

## Running them all

`run.py` builds the wheel, installs it with the `realtime` extra into a fresh virtual environment, then
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
hold there. Those print `SKIP (mock: <why>)` and still run in live mode. The
mock serves no WebSocket, so `realtime-progress` prints `SKIP (mock: no websocket)`
after its submit.

Live mode runs seven small, real jobs per run, and needs a key and a
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

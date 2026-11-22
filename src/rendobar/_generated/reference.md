# Reference
## Jobs
<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">list_job_types</a>() -> ListJobTypesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

List all available job types with their capabilities, cost models, and required inputs. Public — no credential required.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.list_job_types()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_type_schema</a>(...) -> GetJobTypeSchemaResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Get connector-neutral parameter field descriptors for a single active job type. Returns flat typed fields (string, number, boolean, options, or json for nested params) plus the raw JSON Schema for advanced consumers. Used by the no-code connectors to render dynamic forms. Public — no credential required.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_type_schema(
    type="type",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**type:** `str` — Job type identifier (e.g., ffmpeg)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">list_jobs</a>(...) -> ListJobsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

List jobs for the authenticated organization. Supports filtering by status and type, with pagination.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.list_jobs(
    limit=50,
    offset=0,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**status:** `typing.Optional[ListJobsRequestStatus]` — Filter by job status
    
</dd>
</dl>

<dl>
<dd>

**type:** `typing.Optional[str]` — Filter by job type (e.g., ffmpeg)
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Page size (default 50, max 100)
    
</dd>
</dl>

<dl>
<dd>

**offset:** `typing.Optional[int]` — Pagination offset (default 0)
    
</dd>
</dl>

<dl>
<dd>

**sort:** `typing.Optional[ListJobsRequestSort]` — Sort field (default created)
    
</dd>
</dl>

<dl>
<dd>

**order:** `typing.Optional[ListJobsRequestOrder]` — Sort order (default desc)
    
</dd>
</dl>

<dl>
<dd>

**client:** `typing.Optional[str]` — Filter by originating client
    
</dd>
</dl>

<dl>
<dd>

**from:** `typing.Optional[int]` — Created-after (Unix ms)
    
</dd>
</dl>

<dl>
<dd>

**to:** `typing.Optional[int]` — Created-before (Unix ms)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">submit_job</a>(...) -> SubmitJobResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Create a new media processing job. Specify the job type, input files, and processing parameters. Use GET /jobs/types to discover available types.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.submit_job(
    request={
        "type": "ffprobe",
        "params": {
            "command": "https://cdn.rendobar.com/assets/examples/sample.mp4"
        }
    },
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request:** `SubmitJobRequest` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_stats</a>(...) -> GetJobStatsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Aggregate job stats for the authenticated org over a time window.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_stats()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**window:** `typing.Optional[GetJobStatsRequestWindow]` — Window (default 24h). `all` covers the org's whole history.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job</a>(...) -> GetJobResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Retrieve details of a specific job. If the job is complete with an output, includes a download URL.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID (e.g., job_abc123)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">retry_deliveries</a>(...) -> RetryDeliveriesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Put every failed delivery of a completed job back on the queue. Returns how many were retried; zero when nothing had failed or the output is no longer stored.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.retry_deliveries(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">cancel_job</a>(...) -> CancelJobResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Cancel a waiting, dispatched or running job. A running job's upstream execution is stopped too. Completed, failed or already cancelled jobs cannot be cancelled.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.cancel_job(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID to cancel
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">download_job_output</a>(...) -> typing.Iterator[bytes]</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Stream the output file of a completed job. Only available for jobs with status 'complete' and an output file.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.download_job_output(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_logs</a>(...) -> GetJobLogsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Retrieve execution logs for a completed job. Returns structured log entries with timestamps, levels, and step associations.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_logs(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_resources</a>(...) -> GetJobResourcesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Retrieve the recorded resource utilization series (CPU, memory, disk, network, GPU) for a job. Returns an empty array if none were persisted.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_resources(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_metrics</a>(...) -> GetJobMetricsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Deprecated alias for GET /jobs/{id}/resources. Use /resources.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_metrics(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_throughput</a>(...) -> GetJobThroughputResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Retrieve the recorded encode-throughput series (frames per second, realtime speed, frame index) for a job. Returns an empty array if the job produced none (e.g. a non-encode job).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_throughput(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_timings</a>(...) -> GetJobTimingsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns API + runner + queue timing breakdown for a single job. Lazy-loaded — not included in default job response.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_timings(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">get_job_share</a>(...) -> GetJobShareResponse</code></summary>
<dl>
<dd>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.get_job_share(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">create_job_share</a>(...) -> CreateJobShareResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Copies the job output to the public CDN bucket and returns a shareable URL. Requires Pro plan or higher.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.create_job_share(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">delete_job_share</a>(...) -> DeleteJobShareResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Deletes the shared copy from the public bucket and purges CDN cache.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.delete_job_share(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.jobs.<a href="src/rendobar/jobs/client.py">dispute_job</a>(...) -> DisputeJobResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Flags a job charge for manual admin review. All disputes — regardless of amount — go through admin discretion. No automatic refunds.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.jobs.dispute_job(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Job ID
    
</dd>
</dl>

<dl>
<dd>

**reason:** `typing.Optional[str]` — Reason for dispute
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Models
<details><summary><code>client.models.<a href="src/rendobar/models/client.py">list_models</a>(...) -> ListModelsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

List available image.generate, image.edit and image.upscale models with pricing, tier, and capability metadata. Filter to a single job type with ?job=.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.models.list_models(
    job="image.generate",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**job:** `typing.Optional[str]` — Filter to models supporting this job type
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Compose
<details><summary><code>client.compose.<a href="src/rendobar/compose/client.py">validate_compose</a>(...) -> ValidateComposeResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Check the `params` of a compose job without rendering anything. Free, and nothing is stored. Runs the same checks a submit runs, plus the timeline checks a render would otherwise fail on. The response carries the params as a render would read them: defaults filled in, and a timeline written in an older shape rewritten into the current one. It also runs the plan check: a video above your plan is `valid: false` with a problem at `["output"]` whose `upgradeTo` names the plan that renders it. A valid result carries `price`, the rate per minute of output and the fewest seconds a render bills.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.compose.validate_compose(
    params={
        "key": "value"
    },
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**params:** `typing.Dict[str, typing.Any]` — Exactly what you would send as `params` when creating a compose job.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.compose.<a href="src/rendobar/compose/client.py">list_compose_effects</a>() -> ListComposeEffectsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Every built-in effect an `effects` list takes, with its parameters, ranges, units, defaults and which parameters take keyframes. Each looks right written with nothing but its type.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.compose.list_compose_effects()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.compose.<a href="src/rendobar/compose/client.py">list_compose_engine_effects</a>() -> ListComposeEngineEffectsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Every filter an `engine` effect may name, {"type":"engine","filter":"...","params":{...}}, with its parameters and what each accepts. A filter a built-in effect already covers is not listed: use the built-in.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.compose.list_compose_engine_effects()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Billing
<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_billing_state</a>() -> GetBillingStateResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns balance, plan, subscription, usage, and convenience flags for the dashboard.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_billing_state()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_usage_by_client</a>(...) -> GetUsageByClientResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns job count and amount charged grouped by the client that submitted each job (dashboard, sdk, cli, mcp, n8n, api, or a custom tag), over the last N days.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_usage_by_client(
    days="30",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**days:** `typing.Optional[str]` — Lookback window in days (default: 30, max: 365)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">list_transactions</a>(...) -> ListTransactionsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns paginated transaction history with amounts in dollars.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.list_transactions(
    page=1,
    limit=50,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**page:** `typing.Optional[int]` — Page number (default: 1)
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Items per page (default: 50, max: 100)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_usage</a>(...) -> GetUsageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns aggregated usage in dollar amounts for a date range.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_usage(
    start="2026-03-01",
    end="2026-03-13",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**start:** `typing.Optional[str]` — Start date (YYYY-MM-DD). Defaults to first of current month.
    
</dd>
</dl>

<dl>
<dd>

**end:** `typing.Optional[str]` — End date (YYYY-MM-DD). Defaults to today.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">cancel_credit_schedule</a>()</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Stops a recurring monthly credit top-up at the end of the current period. Does not affect the plan subscription.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.cancel_credit_schedule()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">create_credits_checkout</a>(...) -> CreateCreditsCheckoutResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Creates a Polar checkout session for credit purchase. Minimum $10. Pass interval "month" to start a recurring monthly top-up instead of a one-time purchase.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.create_credits_checkout(
    amount=1.1,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**amount:** `float` — Amount in dollars (minimum $10)
    
</dd>
</dl>

<dl>
<dd>

**interval:** `typing.Optional[CreateCreditsCheckoutRequestInterval]` — Omit for a one-time purchase. "month" starts a recurring top-up of the same amount every month.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">create_plan_checkout</a>(...) -> CreatePlanCheckoutResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Starts a paid plan (Pro $9/mo, Studio $29/mo). An org with no plan subscription gets a checkout session. One already on another paid plan has that subscription moved to the new plan, billed or credited pro rata, and no second subscription is opened.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.create_plan_checkout(
    plan="pro",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**plan:** `CreatePlanCheckoutRequestPlan` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">create_pro_checkout</a>() -> CreateProCheckoutResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Deprecated: use POST /billing/checkout/plan with { "plan": "pro" }. Creates a Polar checkout session for Pro subscription ($9/mo).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.create_pro_checkout()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">update_subscription</a>(...) -> UpdateSubscriptionResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Cancel or reactivate a paid plan subscription. cancelAtPeriodEnd=true cancels at period end; false reactivates.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.update_subscription(
    cancel_at_period_end=True,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**cancel_at_period_end:** `bool` — true cancels the subscription at period end; false reactivates it
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">list_invoices</a>(...) -> ListInvoicesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns Polar order history (subscriptions + one-time purchases) for the current organization.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.list_invoices(
    page=1,
    limit=20,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**page:** `typing.Optional[int]` — Page number (default: 1)
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Items per page (default: 20, max: 50)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_invoice_pdf</a>(...)</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Redirects to the invoice PDF for an order, generating the invoice first when none exists. An invoice needs a billing address; the receipt route does not.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_invoice_pdf(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Order ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_receipt_pdf</a>(...)</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Redirects to the receipt PDF for a specific paid order. Every paid order has one, with no billing address needed.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_receipt_pdf(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Order ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">list_payment_methods</a>() -> ListPaymentMethodsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns saved payment methods for the current organization from Polar.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.list_payment_methods()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">get_billing_portal_url</a>() -> GetBillingPortalUrlResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns a pre-authenticated Polar customer portal URL for managing payment methods and subscriptions.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.get_billing_portal_url()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">delete_payment_method</a>(...) -> DeletePaymentMethodResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Remove a saved payment method from the current organization's Polar account.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.delete_payment_method(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Payment method ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.billing.<a href="src/rendobar/billing/client.py">set_default_payment_method</a>(...) -> SetDefaultPaymentMethodResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Marks a saved payment method as the customer's default. Polar charges it for renewals.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.billing.set_default_payment_method(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Payment method ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Notifications
<details><summary><code>client.notifications.<a href="src/rendobar/notifications/client.py">list_notifications</a>() -> ListNotificationsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Newest 50 notifications for the organization, with the calling user's read state. `meta.unread` counts unread among those 50.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.notifications.list_notifications()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.notifications.<a href="src/rendobar/notifications/client.py">mark_notifications_read</a>(...) -> MarkNotificationsReadResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Marks the given notifications read for the calling user. Unknown or other-org ids are ignored.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.notifications.mark_notifications_read(
    ids=[
        "ids"
    ],
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**ids:** `typing.List[str]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Organizations
<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">list_orgs</a>() -> ListOrgsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns all organizations the authenticated user is a member of, with their role in each.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.list_orgs()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">create_org</a>(...) -> CreateOrgResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Create a new organization. The authenticated user becomes its first Owner. A free-tier subscription and $0 balance are provisioned automatically. Maximum 5 organizations per user.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.create_org(
    name="name",
    slug="slug",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**name:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**slug:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">get_current_org</a>() -> GetCurrentOrgResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns complete information about the authenticated organization, including basic details, subscription status, plan configuration (limits, features), and current balance. For plan limits without billing data, use GET /account/capabilities, which needs no scope.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.get_current_org()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">delete_org</a>()</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Permanently delete the authenticated organization and all associated data. Requires the workspace:delete permission (Owner). Cancels any active subscription. This action is irreversible.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.delete_org()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">update_org</a>(...) -> UpdateOrgResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Update the name and/or slug of the authenticated organization. Requires the settings:manage permission (Owner or Admin).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.update_org()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**name:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**slug:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">send_exit_feedback</a>(...) -> SendExitFeedbackResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Optional. Requires the workspace:delete permission (Owner). Sent just before deleting the organization. Stored anonymously, with no organization or user id.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.send_exit_feedback(
    reason="missing_feature",
    comment=None,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**reason:** `SendExitFeedbackRequestReason` 
    
</dd>
</dl>

<dl>
<dd>

**comment:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">get_org_settings</a>() -> GetOrgSettingsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the current organization's settings, including region preference and billing email opt-out.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.get_org_settings()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">update_org_settings</a>(...) -> UpdateOrgSettingsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Update region preference, billing email opt-out and/or the product analytics opt-out for the current organization. Partial patch — omit fields to leave them unchanged. Pinning region 'auto' is rejected; choose a specific region first.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.update_org_settings()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**billing_emails_enabled:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**default_region:** `typing.Optional[UpdateOrgSettingsRequestDefaultRegion]` 
    
</dd>
</dl>

<dl>
<dd>

**region_pinned:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**product_analytics_enabled:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">get_callback_secret</a>() -> GetCallbackSecretResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the org's stable secret for verifying signed per-job callbacks (jobs submitted with callback.verify=true). Generated on first fetch, then stable until rotated. Verify a signed callback with the SDK's verifyWebhook(rawBody, headers, secret) — the scheme is identical.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.get_callback_secret()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">rotate_callback_secret</a>() -> RotateCallbackSecretResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Generates a new callback signing secret and returns it. Callbacks delivered after rotation are signed with the new secret, so update your verifier promptly (there is no dual-secret window).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.rotate_callback_secret()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">list_org_audit_log</a>(...) -> ListOrgAuditLogResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Changes to API keys, members, webhooks, connected storage and workspace settings, newest first. Owners and Admins only, on a plan with the audit log.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.list_org_audit_log()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**before:** `typing.Optional[int]` — Return entries older than this Unix ms, from the previous page's nextBefore
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">invite_org_member</a>(...) -> InviteOrgMemberResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Send an invitation to join the current organization. Needs the Admin or Owner role. Only an Owner can invite an Owner, and only from the dashboard: no API key or connected app can.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.invite_org_member(
    email="teammate@example.com",
    role="owner",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**email:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**role:** `InviteOrgMemberRequestRole` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">invite_org_members</a>(...) -> InviteOrgMembersResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Send invitations to several addresses at once. People already in the workspace, addresses with a live pending invitation, repeats and malformed addresses are skipped and reported in `skipped`. The whole batch has to fit the plan's seats, or none is sent. Needs the Admin or Owner role, or an API key with `team:write`. Only an Owner can invite Owners, and only from the dashboard.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.invite_org_members(
    emails=[
        "teammate@example.com"
    ],
    role="owner",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**emails:** `typing.List[str]` 
    
</dd>
</dl>

<dl>
<dd>

**role:** `InviteOrgMembersRequestRole` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">resend_org_invitation</a>(...) -> ResendOrgInvitationResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Send a pending invitation again and give it a fresh 7 days. Works after it has expired. The person resending becomes the inviter, so accept and decline notices go to them. An invitation that was accepted, declined or revoked cannot be resent. If the email cannot be sent the invitation keeps its old expiry. Only an Owner at the dashboard can resend an Owner invitation.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.resend_org_invitation(
    invitation_id="inv_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**invitation_id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">remove_org_member</a>(...) -> RemoveOrgMemberResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Remove a member from the organization. Admins and Owners remove others, and only an Owner at the dashboard removes an Owner. Any member can remove themselves to leave. A workspace keeps at least one Owner, so its last Owner cannot leave or be removed. Every Owner is emailed when an Owner goes.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.remove_org_member(
    member_id="mem_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**member_id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">update_org_member_role</a>(...) -> UpdateOrgMemberRoleResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Change a member's role. Admins and Owners change Admins and Members. Only an Owner makes someone an Owner or changes an Owner's role, and only from the dashboard: no API key or connected app can. A workspace keeps at least one Owner, so its last Owner cannot be demoted. Every Owner is emailed when the Owners change.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.update_org_member_role(
    member_id="mem_abc123",
    role="owner",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**member_id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**role:** `UpdateOrgMemberRoleRequestRole` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">revoke_org_invitation</a>(...) -> RevokeOrgInvitationResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Cancel a pending invitation. Requires owner or admin role.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.revoke_org_invitation(
    invitation_id="inv_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**invitation_id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.organizations.<a href="src/rendobar/organizations/client.py">preview_invitation</a>(...) -> PreviewInvitationResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Read what an invitation offers before signing in: the workspace, who invited you, the role, and whether it can still be accepted. Public, and it changes nothing.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.organizations.preview_invitation(
    id="inv_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Account
<details><summary><code>client.account.<a href="src/rendobar/account/client.py">get_account_capabilities</a>() -> GetAccountCapabilitiesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Plan limits and enabled features for the authenticated account. Use this to validate input before submitting a job. Contains no billing data.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.account.get_account_capabilities()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## API Keys
<details><summary><code>client.api_keys.<a href="src/rendobar/api_keys/client.py">list_api_keys</a>() -> ListApiKeysResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns every API key in the current workspace, whoever created it, including disabled ones. Key values are never returned after creation. Each key names its creator and its scopes, and says whether the caller may manage it.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.api_keys.list_api_keys()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.api_keys.<a href="src/rendobar/api_keys/client.py">create_api_key</a>(...) -> CreateApiKeyResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Creates a new API key for the current workspace. The key belongs to the workspace and keeps working if its creator leaves. What it may do is its scopes, which never follow its creator's role. The full key value is returned **only once**. Store it securely, it cannot be retrieved again.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.api_keys.create_api_key()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**name:** `typing.Optional[str]` — Descriptive name for the key (defaults to 'API Key')
    
</dd>
</dl>

<dl>
<dd>

**expires_in:** `typing.Optional[int]` — Expiration in seconds (e.g., 2592000 = 30 days). Omit for no expiry.
    
</dd>
</dl>

<dl>
<dd>

**scopes:** `typing.Optional[typing.List[str]]` — What this key may do. Defaults to everything your role can grant. Never more than you can do yourself, and never keys:write, which a key can never hold. `write` includes `read` for the same resource.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.api_keys.<a href="src/rendobar/api_keys/client.py">revoke_api_key</a>(...) -> RevokeApiKeyResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Permanently revokes an API key in the workspace. Needs the Admin or Owner role, whoever created the key. Cannot be undone.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.api_keys.revoke_api_key(
    id="key_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — API key ID to revoke
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.api_keys.<a href="src/rendobar/api_keys/client.py">update_api_key</a>(...) -> UpdateApiKeyResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Rename an API key, or enable or disable it. A key's scopes are fixed when it is created. Disabling immediately blocks the key without deleting it. Needs the Admin or Owner role, whoever created the key.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.api_keys.update_api_key(
    id="key_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**name:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**enabled:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Assets
<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">list_assets</a>(...) -> ListAssetsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns a paginated list of assets for the authenticated organization. Use scope=system to list system-provided assets instead.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.list_assets()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**kind:** `typing.Optional[ListAssetsRequestKind]` — Filter by asset kind
    
</dd>
</dl>

<dl>
<dd>

**scope:** `typing.Optional[ListAssetsRequestScope]` — Filter by scope (defaults to org assets)
    
</dd>
</dl>

<dl>
<dd>

**status:** `typing.Optional[ListAssetsRequestStatus]` — Filter by status
    
</dd>
</dl>

<dl>
<dd>

**lifecycle:** `typing.Optional[ListAssetsRequestLifecycle]` — Filter by lifecycle
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Items per page (default 50, max 100)
    
</dd>
</dl>

<dl>
<dd>

**offset:** `typing.Optional[int]` — Offset for pagination (default 0)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">create_asset</a>(...) -> CreateAssetAnswer</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Creates a pending asset and returns presigned upload URL(s). Files at or below the single-PUT threshold get one PUT URL; larger files get multipart part URLs. If a ready asset with the same checksum already exists, the existing asset is returned (deduplicated).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.create_asset(
    filename="filename",
    size=1,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**filename:** `str` — Original filename
    
</dd>
</dl>

<dl>
<dd>

**size:** `int` — File size in bytes
    
</dd>
</dl>

<dl>
<dd>

**content_type:** `typing.Optional[str]` — MIME content type
    
</dd>
</dl>

<dl>
<dd>

**checksum:** `typing.Optional[str]` — Client-declared sha256 (enables dedup)
    
</dd>
</dl>

<dl>
<dd>

**lifecycle:** `typing.Optional[CreateAssetRequestLifecycle]` — Storage lifecycle (defaults to ephemeral)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">list_asset_templates</a>(...) -> ListAssetTemplatesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Convenience endpoint that returns system-provided PSD templates. Equivalent to GET /assets?scope=system&kind=psd_template.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.list_asset_templates()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Items per page (default 50, max 100)
    
</dd>
</dl>

<dl>
<dd>

**offset:** `typing.Optional[int]` — Offset for pagination (default 0)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">get_asset</a>(...) -> GetAssetResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns a single asset by ID. Users can access their own org's assets and system-scoped assets.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.get_asset(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">delete_asset</a>(...) -> DeleteAssetResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Deletes an asset record and its associated R2 object. System-scoped assets cannot be deleted.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.delete_asset(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">complete_asset_upload</a>(...) -> CompleteAssetUploadResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Verifies the uploaded object exists in storage, enforces the plan size limit and storage quota, and marks the asset ready. For multipart uploads, supply the part etags to assemble the object first.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.complete_asset_upload(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**parts:** `typing.Optional[typing.List[CompleteAssetUploadRequestPartsItem]]` — Multipart part etags (required for multipart uploads)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">download_asset</a>(...) -> DownloadAssetResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns a short-lived presigned GET URL for a ready asset's object.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.download_asset(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">get_asset_content</a>(...)</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Redirects to a short-lived presigned GET URL for a ready asset's object.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.get_asset_content(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.assets.<a href="src/rendobar/assets/client.py">get_asset_preview</a>(...)</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the preprocessed thumbnail PNG for an asset.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.assets.get_asset_preview(
    id="id",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Asset ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Team
<details><summary><code>client.team.<a href="src/rendobar/team/client.py">invite_team_member</a>(...) -> InviteTeamMemberResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Send an invitation to join the organization. Requires owner or admin role.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.team.invite_team_member(
    email="colleague@company.com",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**email:** `str` — Email address to invite
    
</dd>
</dl>

<dl>
<dd>

**role:** `typing.Optional[InviteTeamMemberRequestRole]` — Role for the invited member
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.team.<a href="src/rendobar/team/client.py">update_team_member_role</a>(...) -> UpdateTeamMemberRoleResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Update a member's role within the organization. Requires owner or admin role.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.team.update_team_member_role(
    member_id="mem_abc123",
    role="admin",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**member_id:** `str` — Member ID to update
    
</dd>
</dl>

<dl>
<dd>

**role:** `UpdateTeamMemberRoleRequestRole` — New role for the member
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.team.<a href="src/rendobar/team/client.py">remove_team_member</a>(...) -> RemoveTeamMemberResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Remove a member from the organization. Owner/admin can remove others. Any member can remove themselves (leave).
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.team.remove_team_member(
    member_id="mem_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**member_id:** `str` — Member ID to remove
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.team.<a href="src/rendobar/team/client.py">revoke_team_invitation</a>(...) -> RevokeTeamInvitationResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Cancel a pending invitation. Requires owner or admin role.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.team.revoke_team_invitation(
    invitation_id="inv_abc123",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**invitation_id:** `str` — Invitation ID to revoke
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Webhooks
<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">list_webhook_endpoints</a>() -> ListWebhookEndpointsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns all webhook endpoints for the organization (including inactive). Signing secrets are masked.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.list_webhook_endpoints()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">create_webhook_endpoint</a>(...) -> CreateWebhookEndpointResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Create a new webhook endpoint for the organization. Returns the signing secret in plaintext -- store it securely, it will not be shown again.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.create_webhook_endpoint(
    name="name",
    url="url",
    subscribed_events=[
        "job.created"
    ],
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**name:** `str` — Endpoint name (1-50 chars)
    
</dd>
</dl>

<dl>
<dd>

**url:** `str` — Webhook endpoint URL (HTTPS only)
    
</dd>
</dl>

<dl>
<dd>

**subscribed_events:** `typing.List[CreateWebhookEndpointRequestSubscribedEventsItem]` — Events to subscribe to
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">get_webhook_endpoint</a>(...) -> GetWebhookEndpointResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns a single webhook endpoint by ID. Signing secret is masked.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.get_webhook_endpoint(
    id="whe_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">delete_webhook_endpoint</a>(...)</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Permanently delete a webhook endpoint.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.delete_webhook_endpoint(
    id="whe_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">update_webhook_endpoint</a>(...) -> UpdateWebhookEndpointResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Update an existing webhook endpoint. All fields are optional. Changing the URL resets the failure counter. Re-enabling an endpoint clears the disabled reason and resets the failure counter.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.update_webhook_endpoint(
    id="whe_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**name:** `typing.Optional[str]` — Endpoint name (1-50 chars)
    
</dd>
</dl>

<dl>
<dd>

**url:** `typing.Optional[str]` — Webhook endpoint URL (HTTPS only)
    
</dd>
</dl>

<dl>
<dd>

**subscribed_events:** `typing.Optional[typing.List[UpdateWebhookEndpointRequestSubscribedEventsItem]]` — Events to subscribe to
    
</dd>
</dl>

<dl>
<dd>

**active:** `typing.Optional[bool]` — Enable or disable the endpoint
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">rotate_webhook_secret</a>(...) -> RotateWebhookSecretResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Rotate the signing secret for a webhook endpoint. The previous secret remains valid for 24 hours. Can only be called once per 24 hours.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.rotate_webhook_secret(
    id="whe_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">test_webhook_endpoint</a>(...) -> TestWebhookEndpointResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Send a test webhook event to the endpoint. Works even if the endpoint is disabled. Rate limited to 10 per minute per organization.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.test_webhook_endpoint(
    id="whe_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">list_webhook_deliveries</a>(...) -> ListWebhookDeliveriesResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns webhook deliveries for the organization with optional filters. Includes the endpoint name via JOIN.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.list_webhook_deliveries()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**endpoint_id:** `typing.Optional[str]` — Filter by endpoint ID
    
</dd>
</dl>

<dl>
<dd>

**event:** `typing.Optional[str]` — Filter by event type
    
</dd>
</dl>

<dl>
<dd>

**status:** `typing.Optional[ListWebhookDeliveriesRequestStatus]` — Filter by delivery status
    
</dd>
</dl>

<dl>
<dd>

**job_id:** `typing.Optional[str]` — Filter by job ID
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` — Number of results (1-100, default 50)
    
</dd>
</dl>

<dl>
<dd>

**offset:** `typing.Optional[int]` — Offset for pagination (default 0)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.webhooks.<a href="src/rendobar/webhooks/client.py">retry_webhook_delivery</a>(...) -> RetryWebhookDeliveryResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Manually retry a failed or cancelled webhook delivery. The delivery is re-enqueued for processing.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.webhooks.retry_webhook_delivery(
    id="whd_abc123def456",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` — Webhook delivery ID
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Storage
<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">list_storage</a>() -> ListStorageResponse</code></summary>
<dl>
<dd>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.list_storage()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">create_storage</a>(...) -> CreateStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Connect your own bucket under an id you choose. The credentials are verified with a write, read and delete probe before anything is stored, encrypted at rest, and never returned. For R2, a Cloudflare API token may stand in for the keys: it is exchanged for the key pair it represents and not kept.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.create_storage(
    request={
        "provider": "r2",
        "credentials": {
            "type": "keys",
            "access_key_id": "accessKeyId",
            "secret_access_key": "secretAccessKey"
        },
        "id": "id",
        "bucket": "bucket"
    },
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request:** `CreateStorageRequest` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">look_up_s3bucket</a>(...) -> LookUpS3BucketResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

What an unsigned HEAD can tell you about a bucket before anyone has credentials for it: whether the name is taken, and by which region. It cannot say whether the bucket is yours, because S3 names are global. For the connect form, so a name that will not work is answered in the field rather than two minutes later in the AWS console.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.look_up_s3bucket(
    name="name",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**name:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">list_account_buckets</a>(...) -> ListAccountBucketsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Names only, read through a connection this org already has, so the next bucket can be picked from a list instead of typed. Empty is ordinary rather than an error: an org with no connection on that provider, an AWS role granted before s3:ListAllMyBuckets existed, the bucket-scoped IAM policy we print, or an R2 token scoped to one bucket. The form falls back to a typed name in every one of those cases.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.list_account_buckets()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**provider:** `typing.Optional[ListAccountBucketsRequestProvider]` — Which of this org's connections to ask. Only providers whose account root answers a bucket listing.
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">prepare_aws_storage</a>(...) -> PrepareAwsStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Creates a pending connection and returns a CloudFormation quick-create link. The stack makes a role that trusts Rendobar's own OpenID issuer for this connection alone and reports back; no access keys exist anywhere. The response also carries the trust policy and Terraform for a hand-made role, finished with a PATCH carrying the role ARN.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.prepare_aws_storage(
    id="id",
    bucket="bucket",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**bucket:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**region:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**public_base_url:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**create_bucket:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**access:** `typing.Optional[PrepareAwsStorageRequestAccess]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">start_supabase_storage</a>() -> StartSupabaseStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the Supabase authorization URL to send the person to. When they return, list the projects the sign-in can see with the state, then finish one as a connection. The grant is read twice and forgotten; the vault keeps the project's own S3 session credential.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.start_supabase_storage()

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">get_supabase_session</a>(...) -> GetSupabaseSessionResponse</code></summary>
<dl>
<dd>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.get_supabase_session(
    state="state",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**state:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">list_supabase_buckets</a>(...) -> ListSupabaseBucketsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Read as the project's service role, with the sign-in's grant. The grant stays where it is.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.list_supabase_buckets(
    state="state",
    project_ref="projectRef",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**state:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**project_ref:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">finish_supabase_storage</a>(...) -> FinishSupabaseStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Reads the chosen project's keys with the sign-in's grant, probes the bucket with the project's S3 session credential, stores that credential encrypted, and forgets the grant.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.finish_supabase_storage(
    state="state",
    project_ref="projectRef",
    id="id",
    bucket="bucket",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**state:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**project_ref:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**bucket:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**public_base_url:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**create_bucket:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">get_storage</a>(...) -> GetStorageResponse</code></summary>
<dl>
<dd>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.get_storage(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">delete_storage</a>(...)</code></summary>
<dl>
<dd>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.delete_storage(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">update_storage</a>(...) -> UpdateStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

New credentials are probed before they replace the old ones. Rotation is this update; there is no separate rotate call.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.update_storage(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**credentials:** `typing.Optional[UpdateStorageRequestCredentials]` 
    
</dd>
</dl>

<dl>
<dd>

**public_base_url:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**path_template:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**on_conflict:** `typing.Optional[UpdateStorageRequestOnConflict]` 
    
</dd>
</dl>

<dl>
<dd>

**default_destination:** `typing.Optional[bool]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">test_storage</a>(...) -> TestStorageResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Writes a zero-byte marker, reads it back and deletes it. `ok` reflects the write check; a failed read means sources from this storage will fail; a skipped delete means the connection cannot delete, which is the setup we recommend.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.test_storage(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">get_storage_stats</a>(...) -> GetStorageStatsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Deliveries a day for the last 30 days, measured throughput over recent deliveries, the bytes and files written all time, and the last test write's round trip. Counts and rates only; no object names.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.get_storage_stats(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.storage.<a href="src/rendobar/storage/client.py">list_storage_objects</a>(...) -> ListStorageObjectsResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

One page of folders and files directly under `prefix` (empty for the root). Up to 1000 keys per page; pass `cursor` for the next page. The bucket's own listing permission applies.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.storage.list_storage_objects(
    id="prod-media",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**id:** `str` 
    
</dd>
</dl>

<dl>
<dd>

**prefix:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**cursor:** `typing.Optional[str]` 
    
</dd>
</dl>

<dl>
<dd>

**limit:** `typing.Optional[int]` 
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

## Upload Sessions
<details><summary><code>client.upload_sessions.<a href="src/rendobar/upload_sessions/client.py">get_upload_session</a>(...) -> GetUploadSessionResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Returns the session's status, expiry, and the assets uploaded through it so far. A 'done' session stays viewable here (only 'expired' 410s). The token is the sole credential — no API key required.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.upload_sessions.get_upload_session(
    token="token",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**token:** `str` — Upload session bearer token
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.upload_sessions.<a href="src/rendobar/upload_sessions/client.py">add_upload_session_file</a>(...) -> AddUploadSessionFileResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Creates a pending asset and returns presigned upload URL(s), gated by the session's remaining file count and the org's plan size limit.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.upload_sessions.add_upload_session_file(
    token="token",
    filename="filename",
    size=1,
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**token:** `str` — Upload session bearer token
    
</dd>
</dl>

<dl>
<dd>

**filename:** `str` — Original filename
    
</dd>
</dl>

<dl>
<dd>

**size:** `int` — File size in bytes
    
</dd>
</dl>

<dl>
<dd>

**content_type:** `typing.Optional[str]` — MIME content type
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.upload_sessions.<a href="src/rendobar/upload_sessions/client.py">complete_upload_session_file</a>(...) -> CompleteUploadSessionFileResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Verifies the uploaded object landed in storage and marks the asset ready. assetId must have been returned by a prior POST to this same session.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.upload_sessions.complete_upload_session_file(
    token="token",
    asset_id="assetId",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**token:** `str` — Upload session bearer token
    
</dd>
</dl>

<dl>
<dd>

**asset_id:** `str` — Asset ID returned by POST /files
    
</dd>
</dl>

<dl>
<dd>

**parts:** `typing.Optional[typing.List[CompleteUploadSessionFileRequestPartsItem]]` — Multipart part etags (required for multipart uploads)
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>

<details><summary><code>client.upload_sessions.<a href="src/rendobar/upload_sessions/client.py">complete_upload_session</a>(...) -> CompleteUploadSessionResponse</code></summary>
<dl>
<dd>

#### 📝 Description

<dl>
<dd>

<dl>
<dd>

Marks the session done (the page's finish button). Any MCP tool waiting on this session's completion observes the status flip.
</dd>
</dl>
</dd>
</dl>

#### 🔌 Usage

<dl>
<dd>

<dl>
<dd>

```python
from rendobar import GeneratedClient
from rendobar.environment import GeneratedClientEnvironment

client = GeneratedClient(
    token="<token>",
    environment=GeneratedClientEnvironment.DEFAULT,
)

client.upload_sessions.complete_upload_session(
    token="token",
)

```
</dd>
</dl>
</dd>
</dl>

#### ⚙️ Parameters

<dl>
<dd>

<dl>
<dd>

**token:** `str` — Upload session bearer token
    
</dd>
</dl>

<dl>
<dd>

**request_options:** `typing.Optional[RequestOptions]` — Request-specific configuration.
    
</dd>
</dl>
</dd>
</dl>


</dd>
</dl>
</details>


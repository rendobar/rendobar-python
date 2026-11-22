"""Read what this API key's workspace may do, and what job types exist.

    RENDOBAR_API_KEY=rb_... python main.py

This SDK reads plan limits and features (`account.capabilities()`) and the job
type registry. It has no billing, API key or organization calls yet (see
examples/README.md).
"""
from __future__ import annotations

import os
from typing import NoReturn

from rendobar import Rendobar


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def main() -> None:
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-account-admin") as rb:
        account = rb.account.capabilities()
        limits, features = account.limits, account.features
        print(f"plan: {account.plan.name} ({account.plan.slug})")
        print(f"concurrent jobs: {limits.concurrent_jobs}, longest job: {limits.max_job_timeout} s")
        print(f"webhooks: {features.webhooks}, raw ffmpeg: {features.raw_ffmpeg}, gpu: {features.gpu}")
        if not account.plan.slug or limits.concurrent_jobs < 1:
            fail(f"capabilities {account!r}")

        types = rb.jobs.types()  # the live registry: never hardcode this list
        print(f"job types: {[job_type.type for job_type in types]}")
        if not types:
            fail("no job types")

        first = types[0]
        schema = rb.jobs.schema(first.type)
        print(f"{schema.type}: {first.summary}")
        for field in schema.fields:
            print(f"  {field.key}: {field.type}{' (required)' if field.required else ''}")
        if schema.type != first.type or not schema.fields:
            fail(f"schema of {first.type}: {schema!r}")


if __name__ == "__main__":
    main()

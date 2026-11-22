"""Read the workspace, its billing and usage, manage an API key, change and restore an
org setting, read notifications, and read the job types.

    RENDOBAR_API_KEY=rb_... python main.py

Everything here reads, except two things it undoes: an org setting is flipped
and put back, and an API key is created and revoked. Creating a key needs the
`keys:write` scope, which no API key holds, so with an API key that step
prints a SKIP. An OAuth access token runs it.
"""
from __future__ import annotations

import os
import secrets
from typing import NoReturn

from rendobar import PermissionDeniedError, Rendobar

API_URL = os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com")
MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def account(rb: Rendobar) -> None:
    current = rb.orgs.current()
    capabilities = rb.account.capabilities()
    limits, features = capabilities.limits, capabilities.features
    print(f"org {current.org.name} ({current.org.member_role}) on {capabilities.plan.name}")
    print(f"concurrent jobs: {limits.concurrent_jobs}, longest job: {limits.max_job_timeout} s, webhooks: {features.webhooks}")
    if not current.org.id or limits.concurrent_jobs < 1:
        fail(f"capabilities {capabilities!r}")
    memberships = rb.orgs.list()
    print(f"member of {len(memberships)} organizations")
    if not any(membership.id == current.org.id for membership in memberships):
        fail("the current organization is not in orgs.list()")


def billing(rb: Rendobar) -> None:
    state = rb.billing.state()
    usage = rb.billing.usage()
    print(f"balance ${state.balance.amount:.2f} on {state.plan.name}; "
          f"{usage.total_jobs} jobs this period ({usage.total_amount_formatted})")
    if usage.total_jobs < 0 or state.usage.job_count < 0:
        fail(f"usage {usage!r}")
    by_client = rb.billing.usage_by_client(days=30)
    print(f"usage by client: {[(row.client, row.job_count) for row in by_client]}")
    transactions = rb.billing.transactions(limit=5)
    print(f"{transactions.meta.total} transactions, newest: {[(t.type, t.amount) for t in transactions]}")
    if transactions.meta.total < len(transactions):
        fail(f"transactions meta {transactions.meta!r}")
    invoices = rb.billing.history(limit=5)
    print(f"{invoices.meta.total} invoices")


def api_keys(rb: Rendobar) -> None:
    keys = rb.api_keys.list()
    print(f"{len(keys)} API keys: {[key.prefix for key in keys]}")
    try:
        key = rb.api_keys.create(name=f"example-{secrets.token_hex(4)}", scopes=["jobs:read"], expires_in=3600)
    except PermissionDeniedError as err:
        if err.code != "INSUFFICIENT_SCOPE":
            raise
        print(f"SKIP (live: {err.message} An API key cannot create keys.)")
        return
    try:
        if MOCK:
            print("SKIP (mock: the key value is a placeholder)")
        elif not key.key.startswith("rb_"):
            fail("a new key does not start with rb_")
        if not any(each.id == key.id for each in rb.api_keys.list()):
            fail("the new key is not listed")
        if not MOCK:
            with Rendobar(key.key, base_url=API_URL, app="example-account-admin") as scoped:
                print(f"key {key.prefix}... reads jobs: {scoped.jobs.list(limit=1).meta.total} in total")
    finally:
        if not rb.api_keys.revoke(key.id).revoked:
            fail(f"key {key.id} was not revoked")
        print(f"revoked key {key.id}")


def settings(rb: Rendobar) -> None:
    before = rb.orgs.get_settings()
    print(f"billing emails {before.billing_emails_enabled}, region {before.default_region}")
    try:
        changed = rb.orgs.update_settings(billing_emails_enabled=not before.billing_emails_enabled)
        if MOCK:
            print("SKIP (mock: settings do not change)")
        elif changed.billing_emails_enabled == before.billing_emails_enabled:
            fail("update_settings did not change billing emails")
    finally:
        restored = rb.orgs.update_settings(billing_emails_enabled=before.billing_emails_enabled)
        if restored.billing_emails_enabled != before.billing_emails_enabled:
            fail("billing emails were not restored")
        print(f"billing emails restored to {restored.billing_emails_enabled}")


def notifications(rb: Rendobar) -> None:
    page = rb.notifications.list()
    print(f"{len(page)} notifications, {page.meta.unread} unread")
    if page.meta.unread < 0:
        fail(f"notifications meta {page.meta!r}")
    # Mark one that is already read again: a no-op, so your inbox is left as it was.
    already = [item.id for item in page if item.read]
    if not already:
        print("SKIP (no notification is read yet, and marking an unread one would change the inbox)")
        return
    marked = rb.notifications.mark_read(already[:1])
    print(f"marked {marked.read} notification read")
    if marked.read < 0:
        fail(f"mark_read answered {marked!r}")


def job_types(rb: Rendobar) -> None:
    types = rb.jobs.types()  # the live registry: never hardcode this list
    print(f"job types: {[job_type.type for job_type in types]}")
    if not types:
        fail("no job types")
    first = types[0]
    schema = rb.jobs.schema(first.type)
    print(f"{schema.type}: {', '.join(field.key for field in schema.fields)}")
    if schema.type != first.type or not schema.fields:
        fail(f"schema of {first.type}: {schema!r}")


def main() -> None:
    with Rendobar(base_url=API_URL, app="example-account-admin") as rb:
        account(rb)
        billing(rb)
        api_keys(rb)
        settings(rb)
        notifications(rb)
        job_types(rb)


if __name__ == "__main__":
    main()

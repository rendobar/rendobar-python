"""Writes fern/overrides.yml from fern/openapi.json. Run before every `fern generate`.

The published spec stays as published: the overrides only add types for the
SDK, and every one is derived from the spec, so a new job type needs no edit
here.

`SubmitTypedJob` is the union the SDK's `jobs.create()` takes for a job type
it knows: one variant per typed submit schema (a member of the POST /jobs body
whose `type` is a `const`), holding what to run and nothing else: `type` (as a
literal, which Fern otherwise types as `Literal[...] | Any`), `params` and
`inputs`. Submit options (idempotency key, label, destinations, callback,
force_async) are keyword arguments of `jobs.create()`, so the variants leave
them out and setting one in the job is a type error, not a second way. A job
type the SDK does not know yet goes through `SubmitAnyJob` (the SDK's
`UntypedJob`), which stays out of the union.

Every string enum a response can carry (a job's output category, currency,
file type, delivery status, failed phase; the submit statuses; webhook data)
is typed `str`. Fern types an enum as
`Literal[...] | Any`, which turns off checking, and a closed Literal would
make an older SDK fail on a value the API adds later. `str` is what both
checkers make of `Literal[...] | str`: typed, and open to new values. The
status a job is discriminated on, and the event a webhook is, stay literals.

Usage: python fern/derive_overrides.py [--check]
--check exits 1 when overrides.yml is not what the spec gives (CI runs this).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
SPEC = HERE / "openapi.json"
OUT = HERE / "overrides.yml"
REF = "#/components/schemas/"
WHAT = ("type", "params", "inputs")  # what to run; everything else is a submit option


def variant_name(submit_schema: str) -> str:
    """`SubmitFfprobeJob` -> `FfprobeJob`, whose TypedDict Fern names `FfprobeJobParams`."""
    return submit_schema.removeprefix("Submit")


def derive(spec: dict) -> dict:
    body = spec["paths"]["/jobs"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    members = body.get("anyOf") or body.get("oneOf")
    if not members:
        raise SystemExit("POST /jobs body is not a union: the submit layout changed, update derive_overrides.py")
    schemas = spec["components"]["schemas"]
    typed, untyped = [], []
    for member in members:
        name = member["$ref"].removeprefix(REF)
        const = schemas[name].get("properties", {}).get("type", {}).get("const")
        (typed if isinstance(const, str) else untyped).append((name, const))
    if not typed or len(untyped) != 1:
        raise SystemExit(f"expected typed submits plus one untyped one, got typed={typed} untyped={untyped}")
    added: dict = {}
    for name, const in typed:
        schema = schemas[name]
        what = {k: v for k, v in schema["properties"].items() if k in WHAT}
        what["type"] = {"x-fern-type": f'literal<"{const}">', "description": "Job type"}
        added[variant_name(name)] = {
            "type": "object",
            "description": schema.get("description", f"A {const} job."),
            "required": [k for k in schema.get("required", []) if k in WHAT],
            "properties": what,
        }
    added["SubmitTypedJob"] = {
        "description": "A job of a type this SDK knows: what to run, typed per job type.",
        "anyOf": [{"$ref": f"{REF}{variant}"} for variant in added],
    }
    clash = sorted(set(added) & set(schemas))
    if clash:
        raise SystemExit(f"the spec now has schemas named {clash}: rename the derived ones")
    overrides: dict = {"components": {"schemas": added}}
    for name, override in open_enums(spec).items():
        merge(overrides["components"]["schemas"].setdefault(name, {}), override)
    return overrides


def merge(into: dict, more: dict) -> None:
    for key, value in more.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            merge(into[key], value)
        else:
            into[key] = value


def _string_enum(node: dict) -> bool:
    return "enum" in node and all(isinstance(value, str) for value in node["enum"])


def open_enums(spec: dict) -> dict:
    """`{schema: override}` setting `x-fern-type: string` on every string enum a response can carry.

    The roots are the Job union's variants, the webhook payload union's
    variants (each skipping the property its union is discriminated on) and
    the POST /jobs success bodies.
    """
    schemas = spec["components"]["schemas"]
    out: dict = {}

    def walk(node: dict, override: dict, skip: object, seen: frozenset) -> None:
        if "$ref" in node:
            name = node["$ref"].removeprefix(REF)
            if name in seen:
                return
            target = schemas[name]
            if _string_enum(target):
                out.setdefault(name, {})["x-fern-type"] = "string"
            else:
                walk(target, out.setdefault(name, {}), None, seen | {name})
            return
        if any(key in node for key in ("anyOf", "oneOf", "allOf")):
            raise SystemExit("a union inside a response: teach derive_overrides.py to override inside it")
        for prop, child in node.get("properties", {}).items():
            if prop == skip:
                continue
            if _string_enum(child):
                override.setdefault("properties", {}).setdefault(prop, {})["x-fern-type"] = "string"
            else:
                walk(child, override.setdefault("properties", {}).setdefault(prop, {}), None, seen)
        items = node.get("items")
        if isinstance(items, dict):
            if _string_enum(items):
                override.setdefault("items", {})["x-fern-type"] = "string"
            else:
                walk(items, override.setdefault("items", {}), None, seen)

    for union in ("Job", "WebhookPayload"):
        discriminant = schemas[union]["discriminator"]["propertyName"]
        for variant in schemas[union]["oneOf"]:
            name = variant["$ref"].removeprefix(REF)
            walk(schemas[name], out.setdefault(name, {}), discriminant, frozenset({name}))
    for status in ("200", "201"):
        data = spec["paths"]["/jobs"]["post"]["responses"][status]["content"]["application/json"]["schema"]["properties"]["data"]
        for member in data.get("anyOf", [data]):
            walk(member, {}, None, frozenset())
    return {name: prune(o) for name, o in out.items() if prune(o)}


def prune(node: dict) -> dict:
    """Drops the empty branches the walk opened, so the overrides hold only what they change."""
    out = {}
    for key, value in node.items():
        value = prune(value) if isinstance(value, dict) else value
        if value != {}:
            out[key] = value
    return out


def main() -> None:
    text = "# Generated by fern/derive_overrides.py from openapi.json. Do not edit.\n"
    text += json.dumps(derive(json.loads(SPEC.read_text(encoding="utf-8"))), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit("fern/overrides.yml is stale: run python fern/derive_overrides.py")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

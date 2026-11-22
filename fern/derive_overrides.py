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

Each typed job's `inputs` is typed as the input forms the API accepts (a URL,
`{url}`, `{content}` for inline text, `{job}` for another job's output, or a
list of those), defined once here as `InputSource` and `JobInput` until the
spec names them. The spec types inputs as a free-form object.

Fern types an operation's answer from its first 2xx response only. Where the
2xx responses are different components (POST /assets: 200 deduplicated, 201
presigned or multipart), the first one would refuse the others, so each such
operation gets `<OperationId>Answer`, the union of all of them, as its 200
schema.

A list's `meta.pages` is read as optional. The API added it after the rest of
the meta, so a server (or the conformance mock) that predates it must still
read as a page, rather than refusing the whole list over a count.

Enum and `Any` annotations are tightened after generation by postprocess.py.

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

# The input forms the API accepts for every job type, not yet named in the spec.
_SOURCE_FORMS = {
    "InputUrl": ("url", "A file URL, the same as giving the URL as a string"),
    "InputContent": ("content", "Inline text the job reads as a file, such as subtitles or a script"),
    "InputJobOutput": ("job", "The output of another job, by its id (job_...)"),
}
INPUT_SCHEMAS: dict = {
    **{name: {"type": "object", "description": text, "required": [key], "properties": {key: {"type": "string"}}}
       for name, (key, text) in _SOURCE_FORMS.items()},
    "InputSource": {
        "description": "One input file: a URL, or one of the object forms",
        "oneOf": [{"type": "string", "description": "A public or signed URL"}] + [{"$ref": f"{REF}{n}"} for n in _SOURCE_FORMS],
    },
    "JobInput": {
        "description": "A named input: one source, or a list of them for an input that takes several (such as image.edit images)",
        "oneOf": [{"$ref": f"{REF}InputSource"}, {"type": "array", "items": {"$ref": f"{REF}InputSource"}}],
    },
}


def variant_name(submit_schema: str) -> str:
    """`SubmitFfprobeJob` -> `FfprobeJob`, whose TypedDict Fern names `FfprobeJobParams`."""
    return submit_schema.removeprefix("Submit")


def _refs(schema: dict) -> list:
    """The component refs `schema` is: itself when a ref, its members when a oneOf of refs, else none."""
    if set(schema) == {"$ref"}:
        return [schema]
    members = schema.get("oneOf") or []
    return list(members) if members and all(set(m) == {"$ref"} for m in members) else []


def answer_unions(spec: dict) -> tuple:
    """`<OperationId>Answer` unions, and the paths override pointing each operation's 200 at its union."""
    schemas: dict = {}
    paths: dict = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            answers = [r for code, r in sorted(operation.get("responses", {}).items()) if code.startswith("2")]
            found = [_refs(a.get("content", {}).get("application/json", {}).get("schema", {})) for a in answers]
            if len(found) < 2 or not all(found) or "200" not in operation["responses"]:
                continue
            members = [ref for refs in found for ref in refs]
            if len({m["$ref"] for m in members}) < 2:
                continue
            op_id = operation["operationId"]
            name = f"{op_id[:1].upper()}{op_id[1:]}Answer"
            schemas[name] = {"description": f"Every successful answer of {method.upper()} {path}.", "oneOf": members}
            paths.setdefault(path, {})[method] = {"responses": {"200": {"content": {"application/json": {
                "schema": {"$ref": f"{REF}{name}"}}}}}}
    return schemas, paths


def _merge(into: dict, more: dict) -> None:
    for key, value in more.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            _merge(into[key], value)
        else:
            into[key] = value


def optional_pages(spec: dict) -> dict:
    """The paths override reading `meta.pages` of every list as an optional integer."""
    paths: dict = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            for code, response in operation.get("responses", {}).items():
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                if code.startswith("2") and "pages" in schema.get("properties", {}).get("meta", {}).get("properties", {}):
                    pages = {"properties": {"meta": {"properties": {"pages": {"x-fern-type": "optional<integer>"}}}}}
                    _merge(paths, {path: {method: {"responses": {code: {"content": {"application/json": {"schema": pages}}}}}}})
    return paths


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
        if "inputs" in what:
            what["inputs"] = {**what["inputs"], "additionalProperties": {"$ref": f"{REF}JobInput"}}
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
    added.update(INPUT_SCHEMAS)
    unions, paths = answer_unions(spec)
    added.update(unions)
    _merge(paths, optional_pages(spec))
    clash = sorted(set(added) & set(schemas))
    if clash:
        raise SystemExit(f"the spec now has schemas named {clash}: rename the derived ones (or use the spec's)")
    return {"components": {"schemas": added}, "paths": paths}


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

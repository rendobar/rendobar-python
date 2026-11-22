"""Tightens the types Fern generates, after every `fern generate`. CI runs it with --check.

Fern renders every enum as `Literal[...] | Any` and every free-form JSON value
as `Any`, which turns type checking off where a user touches them. This step
rewrites only type annotations in the generated model modules, never logic:

- An enum a response can carry becomes `Literal[...] | str`: typed, and open to
  values the API adds later, so an older SDK keeps parsing.
- An enum only requests use becomes a closed `Literal[...]`, so a misspelt
  value fails the type check.
- `Any` in a model or request TypedDict becomes `object`, so reading a
  free-form value (`job.params`, `job.output.data`) makes you narrow it first.

Which enums a response can carry is derived from the SDK itself: every
generated model module the hand-written layer imports, and every module those
import in turn. Nothing here lists a type by name, so a regeneration needs no
edit.

Usage: python fern/postprocess.py [--check]
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "rendobar"
GENERATED = ROOT / "_generated"
ENUM = re.compile(r"=\s*typing\.Union\[\s*typing\.Literal\[(?P<values>.*?)\],\s*typing\.Any,?\s*\]", re.S)
ANY = re.compile(r"\btyping\.Any\b")


def is_model(path: Path) -> bool:
    """Generated models and request TypedDicts: the files under a `types` or `requests` package."""
    return path.name != "__init__.py" and ({"types", "requests"} & set(path.relative_to(GENERATED).parts[:-1])) != set()


def module_of(path: Path) -> str:
    return ".".join(path.relative_to(ROOT.parent).with_suffix("").parts)


def imports(path: Path) -> set:
    """The generated modules `path` imports (relative or absolute)."""
    found = set()
    package = module_of(path).rsplit(".", 1)[0]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            parts = package.split(".")
            parts = parts[: len(parts) - (node.level - 1)] + ([node.module] if node.module else [])
            name = ".".join(parts)
        else:
            name = node.module or ""
        if name.startswith("rendobar._generated"):
            found.add(name)
    return found


def response_modules() -> set:
    """Model modules a response can reach: what the hand-written layer imports from _generated, transitively."""
    hand = [p for p in ROOT.rglob("*.py") if GENERATED not in p.parents]
    todo = [m for p in hand for m in imports(p) if ".requests." not in m and ".types." in m]
    seen = set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        file = ROOT.parent / Path(*name.split(".")).with_suffix(".py")
        if file.exists():
            todo.extend(m for m in imports(file) if ".requests." not in m)
    return seen


def rewrite(path: Path, open_to_new: bool) -> str:
    text = path.read_text(encoding="utf-8")

    def enum(match: "re.Match[str]") -> str:
        values = " ".join(match.group("values").split()).rstrip(",")
        return f"= typing.Union[typing.Literal[{values}], str]" if open_to_new else f"= typing.Literal[{values}]"

    return ANY.sub("object", ENUM.sub(enum, text))


def main() -> None:
    responses = response_modules()
    stale = []
    for path in sorted(GENERATED.rglob("*.py")):
        if not is_model(path):
            continue
        before = path.read_text(encoding="utf-8")
        after = rewrite(path, module_of(path) in responses)
        if after != before:
            stale.append(path)
            if "--check" not in sys.argv:
                path.write_text(after, encoding="utf-8", newline="\n")
    if "--check" in sys.argv and stale:
        raise SystemExit(f"{len(stale)} generated files are not post-processed: run python fern/postprocess.py")
    if "--check" not in sys.argv:
        print(f"post-processed {len(stale)} files")


if __name__ == "__main__":
    main()

"""The README's code runs as written, and the attributes it reads exist on the real models."""
import builtins
import importlib.util
import os
import re
import typing
import urllib.request
from pathlib import Path

import pytest

from rendobar import AsyncRendobar, JobComplete, Rendobar

README = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
BLOCKS = re.findall(r"```python\n(.*?)```", README, flags=re.S)
MOCK = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")


@pytest.mark.parametrize("block", BLOCKS, ids=[f"block{i}" for i in range(len(BLOCKS))])
def test_every_python_block_runs_as_a_script(block: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each block, pasted into a file on its own, runs: against the conformance mock instead of the API."""
    for extra in ("langchain", "crewai"):
        imports_it = re.search(rf"^from (rendobar\.agents\.)?{extra}\b", block, flags=re.M)
        if imports_it and importlib.util.find_spec(extra) is None:
            pytest.skip(f"needs the {extra} extra")
    # The blocks use the default base_url. Point the default, not the blocks, at the mock.
    for client in (Rendobar, AsyncRendobar):
        defaults = client.__init__.__kwdefaults__
        assert defaults is not None
        monkeypatch.setattr(client.__init__, "__kwdefaults__", {**defaults, "base_url": MOCK})
    monkeypatch.setenv("RENDOBAR_API_KEY", "rb_readme")
    monkeypatch.setenv("RENDOBAR_WEBHOOK_SECRET", "whsec_readme")
    urllib.request.urlopen(urllib.request.Request(f"{MOCK}/__reset", method="POST"), timeout=5)
    exec(compile(block, "README.md", "exec"), {"__name__": "__main__"})  # noqa: S102 (our own README)


def _field_type(model: type, name: str) -> type:
    hints = typing.get_type_hints(model)
    assert name in hints, f"{model.__name__} has no {name}"
    hint = hints[name]
    args = [a for a in typing.get_args(hint) if a is not type(None)]
    return args[0] if args else hint


def test_quickstart_path_output_files_url_exists() -> None:
    output = _field_type(JobComplete, "output")
    file = _field_type(output, "files")  # the List item type
    assert "url" in typing.get_type_hints(file)


def test_every_error_the_readme_names_is_exported() -> None:
    import rendobar

    named = set(re.findall(r"`([A-Za-z]+Error)`", README)) - set(dir(builtins))
    assert {"APIConnectionError", "APITimeoutError", "JobFailedError", "ConflictError", "InvalidArgumentError"} <= named
    for name in named:
        assert name in rendobar.__all__ and issubclass(getattr(rendobar, name), rendobar.RendobarError), name


def test_the_job_options_table_lists_every_run_option() -> None:
    import inspect

    from rendobar import AsyncJobs, Jobs

    section = README.split("## Job options", 1)[1].split("\n## ", 1)[0]
    documented = set(re.findall(r"^\| `(\w+)` \|", section, flags=re.M))
    for method in (Jobs.run, AsyncJobs.run):
        params = set(inspect.signature(method).parameters) - {"self"}
        assert documented == params, (method.__qualname__, documented ^ params)

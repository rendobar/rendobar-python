"""The README's code compiles, and the attributes it reads exist on the real models."""
import ast
import re
import typing
from pathlib import Path

from rendobar import JobComplete

README = (Path(__file__).parent.parent / "README.md").read_text()


def test_every_python_block_compiles() -> None:
    blocks = re.findall(r"```python\n(.*?)```", README, flags=re.S)
    assert len(blocks) >= 3
    for block in blocks:
        compile(block, "README.md", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


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

    named = set(re.findall(r"`([A-Za-z]+Error)`", README))
    assert {"APIConnectionError", "APITimeoutError", "JobFailedError", "ConflictError"} <= named
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

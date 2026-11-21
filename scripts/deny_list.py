"""Fail if a public file names Rendobar internals.

This repo is public and only ever reads the public spec, so internals have no
way in except by hand. This is the check for that hand.
"""
import pathlib
import re
import sys

DENY = [
    r"apps/api/", r"apps/runner", r"packages/shared", r"packages/runner-core",  # monorepo paths
    r"\btrigger\.dev\b", r"\bmodal\.com\b", r"\binfisical\b",  # infrastructure vendors
    r"\bshotcut\b", r"\bmelt\b", r"\bmlt\b",  # the compose engine is not public
    r"api-staging\.rendobar\.com", r"\.workers\.dev\b",  # internal hosts
]
SKIP = {".git", "dist", ".venv", "__pycache__", "node_modules"}

hits = []
for path in pathlib.Path(".").rglob("*"):
    if not path.is_file() or SKIP & set(path.parts) or path.suffix in {".whl", ".png", ".jpg"}:
        continue
    if path.as_posix() == "scripts/deny_list.py":
        continue
    text = path.read_text(errors="ignore")
    for pattern in DENY:
        for m in re.finditer(pattern, text, flags=re.I):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{path}:{line}: {m.group(0)}")
print("\n".join(hits) if hits else "deny-list: clean")
sys.exit(1 if hits else 0)

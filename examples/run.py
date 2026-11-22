"""Type-check and run every example project against the built wheel, in a fresh virtual environment.

    python examples/run.py --mode mock   # default: the conformance mock at RENDOBAR_MOCK (http://127.0.0.1:4100)
    python examples/run.py --mode live   # RENDOBAR_API_KEY and RENDOBAR_API_URL must be set: runs real, billed jobs

Needs uv. Exits non-zero when any example fails its type check or its run.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

EXAMPLES = Path(__file__).resolve().parent
ROOT = EXAMPLES.parent
VECTORS = ROOT / "tests" / "fixtures" / "webhook-vectors.json"
# Each project and the arguments its run takes.
PROJECTS: Dict[str, List[str]] = {
    "quickstart": [],
    "upload-process-download": [],
    "batch-worker": [],
    "webhook-receiver": ["--self-test"],
    "account-admin": [],
}


def sh(cmd: List[str], cwd: Path, env: Dict[str, str] | None = None) -> bool:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, env=env).returncode == 0


def install(tmp: Path) -> Path:
    """Build the wheel, install it into a new venv with the type checkers, and return that venv's python."""
    if not sh(["uv", "build", "--wheel", "--out-dir", str(tmp / "dist")], ROOT):
        sys.exit("FAIL: the wheel did not build")
    wheel = next((tmp / "dist").glob("rendobar-*.whl"))
    python = tmp / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not (sh(["uv", "venv", str(tmp / "venv")], tmp)
            and sh(["uv", "pip", "install", "--python", str(python), str(wheel), "pyright", "mypy"], tmp)):
        sys.exit("FAIL: could not install the wheel")
    where = subprocess.run([str(python), "-I", "-c", "import rendobar; print(rendobar.__file__)"],
                           cwd=tmp, capture_output=True, text=True, check=True).stdout.strip()
    if not Path(where).resolve().is_relative_to((tmp / "venv").resolve()):
        sys.exit(f"FAIL: rendobar imported from {where}, not the installed wheel")
    print(f"rendobar from {where}", flush=True)
    return python


def reset(mock: str) -> None:
    urllib.request.urlopen(urllib.request.Request(f"{mock}/__reset", method="POST"), timeout=5)


def post(url: str, body: bytes, headers: Dict[str, str]) -> int:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as err:
        return err.code


def served_receiver_takes_the_vectors(python: Path, env: Dict[str, str]) -> bool:
    """Start the webhook receiver as a server holding the shared vectors' secret, and post their body to it."""
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server_env = dict(env, RENDOBAR_WEBHOOK_SECRET=vectors["secret"], PORT=str(port))
    server = subprocess.Popen([str(python), "-I", "main.py"], cwd=EXAMPLES / "webhook-receiver", env=server_env)
    url = f"http://127.0.0.1:{port}/rendobar-webhook"
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        body = vectors["body"].encode()
        now = int(time.time())
        digest = hmac.new(vectors["secret"].encode(), f"{now}.".encode() + body, hashlib.sha256).hexdigest()
        fresh = post(url, body, {"X-Rendobar-Timestamp": str(now), "X-Rendobar-Signature": f"sha256={digest}"})
        valid = next(case for case in vectors["cases"] if case["name"] == "valid")
        stale = post(url, body, valid["headers"])  # signed at the vectors' timestamp, long past the tolerance
        print(f"shared vector body, signed now: {fresh}; the vectors' own (old) signature: {stale}")
        return fresh == 204 and stale == 401
    finally:
        server.terminate()
        server.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    mode = parser.parse_args().mode

    env = dict(os.environ, RENDOBAR_EXAMPLES_MODE=mode)
    mock = os.environ.get("RENDOBAR_MOCK", "http://127.0.0.1:4100")
    if mode == "mock":
        env.update(RENDOBAR_API_URL=mock, RENDOBAR_API_KEY="rb_examples")
    elif not (os.environ.get("RENDOBAR_API_KEY") and os.environ.get("RENDOBAR_API_URL")):
        sys.exit("FAIL: live mode needs RENDOBAR_API_KEY and RENDOBAR_API_URL (point it at staging, not production)")

    results: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as folder:
        python = install(Path(folder))
        for name, args in PROJECTS.items():
            project = EXAMPLES / name
            print(f"\n== {name} ({mode})", flush=True)
            if not (sh([str(python), "-m", "pyright", "--pythonpath", str(python), "-p", "."], project)
                    and sh([str(python), "-m", "mypy", "--strict", "main.py"], project)):
                results[name] = "FAIL (types)"
                continue
            if mode == "mock":
                reset(mock)
            ok = sh([str(python), "-I", "main.py", *args], project, env)
            if ok and name == "webhook-receiver":
                ok = served_receiver_takes_the_vectors(python, env)
            results[name] = "PASS" if ok else "FAIL"

    print(f"\nexamples ({mode}):")
    for name, result in results.items():
        print(f"  {name}: {result}")
    if any(result != "PASS" for result in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()

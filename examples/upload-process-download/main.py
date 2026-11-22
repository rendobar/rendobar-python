"""Trim and transcode a video with ffmpeg, then stream the result to disk.

    RENDOBAR_API_KEY=rb_... python main.py [output.mp4]

This SDK has no uploads or assets yet, so the input is a public URL rather than
a local file (see examples/README.md).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from rendobar import Rendobar

VIDEO_URL = "https://cdn.rendobar.com/assets/examples/sample.mp4"
# One second, scaled down, no audio: a cheap job.
COMMAND = f"ffmpeg -i {VIDEO_URL} -t 1 -vf scale=320:-2 -c:v libx264 -preset ultrafast -an clip.mp4"


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def process(rb: Rendobar, target: Path) -> None:
    created = rb.jobs.create({"type": "ffmpeg", "params": {"command": COMMAND, "timeout": 120}}, label="example trim")
    print(f"job {created.id}: {created.status}")

    # throw_on_failure=True: a failed or cancelled job raises JobFailedError, so `job` is a JobComplete.
    job = rb.jobs.wait(created.id, timeout=300, throw_on_failure=True)
    print(f"job {job.id}: {job.status}")
    headline = job.output.file
    if headline is None:
        fail("the job has no output file")
    print(f"output: {headline.path}, {headline.size} bytes")
    if headline.size <= 0:
        fail(f"output size {headline.size}")

    written = rb.jobs.download(job.id, target)
    on_disk = target.stat().st_size
    print(f"downloaded {written} bytes to {target}")
    if written <= 0 or written != on_disk:
        fail(f"wrote {written} bytes, {on_disk} on disk")


def main() -> None:
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-upload-process-download") as rb:
        if len(sys.argv) > 1:
            process(rb, Path(sys.argv[1]))
            return
        with tempfile.TemporaryDirectory() as folder:
            process(rb, Path(folder) / "clip.mp4")


if __name__ == "__main__":
    main()

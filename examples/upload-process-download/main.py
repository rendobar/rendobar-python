"""Upload a local clip, trim and transcode it, stream the result to disk, then list, read and delete the asset.

    RENDOBAR_API_KEY=rb_... python main.py [output.mp4]

The clip is `examples/fixtures/clip.mp4`: two seconds of a test pattern with a
tone, 18 KB. The uploaded asset is ephemeral (it expires on its own after 24
hours) and is deleted at the end anyway, also when a step fails.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List, NoReturn, Optional

from rendobar import Rendobar, UploadProgress

CLIP = Path(__file__).resolve().parent.parent / "fixtures" / "clip.mp4"
PUBLIC_CLIP = "https://cdn.rendobar.com/assets/examples/sample.mp4"
MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"
# One second, scaled down: a cheap job. Each inputs key is a file name the command uses.
COMMAND = "ffmpeg -i clip.mp4 -t 1 -vf scale=160:-2 -c:v libx264 -preset veryfast -c:a aac output.mp4"


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def upload(rb: Rendobar) -> Optional[str]:
    """Upload the clip and return its asset id, or None in mock mode."""
    if MOCK:
        print("SKIP (mock: POST /assets answers no presigned upload, so no bytes can be sent)")
        return None
    progress: List[UploadProgress] = []
    asset = rb.uploads.create(CLIP, content_type="video/mp4", on_progress=progress.append)
    print(f"uploaded {asset.id}: {asset.size_bytes} bytes, {asset.status}")
    size = CLIP.stat().st_size
    if asset.status != "ready" or asset.size_bytes != size:
        fail(f"asset {asset.id} is {asset.status} with {asset.size_bytes} bytes, expected ready with {size}")
    if not progress or progress[-1] != UploadProgress(size, size):
        fail(f"progress reported {progress}")
    return asset.id


def process(rb: Rendobar, source: str, target: Path) -> None:
    created = rb.jobs.create({"type": "ffmpeg", "inputs": {"clip.mp4": source}, "params": {"command": COMMAND, "timeout": 120}},
                             label="example trim")
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

    # Streamed to disk, never held in memory.
    written = rb.jobs.download(job.id, target)
    on_disk = target.stat().st_size
    print(f"downloaded {written} bytes to {target}")
    if written <= 0 or written != on_disk:
        fail(f"wrote {written} bytes, {on_disk} on disk")
    if not MOCK and written != headline.size:
        fail(f"downloaded {written} bytes of a {headline.size} byte output")


def tidy_up(rb: Rendobar, asset_id: Optional[str]) -> None:
    """Find the asset in the list, read it and delete it. In mock mode, the first listed asset."""
    page = rb.assets.list(limit=50)
    listed = page.data[0] if MOCK and page.data else next((asset for asset in page if asset.id == asset_id), None)
    if listed is None:
        fail(f"asset {asset_id} is missing from assets.list")
    read = rb.assets.get(listed.id)
    if read.id != listed.id:
        fail(f"assets.get({listed.id}) returned {read.id}")
    if not rb.assets.delete(listed.id).deleted:
        fail(f"asset {listed.id} was not deleted")
    print(f"deleted asset {read.id} ({read.filename})")


def main() -> None:
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-upload-process-download") as rb:
        asset_id = upload(rb)
        try:
            # An uploaded asset is a job input by reference.
            source = f"asset://{asset_id}" if asset_id is not None else PUBLIC_CLIP
            if len(sys.argv) > 1:
                process(rb, source, Path(sys.argv[1]))
            else:
                with tempfile.TemporaryDirectory() as folder:
                    process(rb, source, Path(folder) / "output.mp4")
            tidy_up(rb, asset_id)
            asset_id = None
        finally:
            if asset_id is not None:  # a step above failed: do not leave the upload behind
                rb.assets.delete(asset_id)


if __name__ == "__main__":
    main()

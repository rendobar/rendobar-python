"""Probe a public video and print its duration, resolution and codecs.

    RENDOBAR_API_KEY=rb_... python main.py
"""
from __future__ import annotations

import os
from typing import NoReturn

from rendobar import FfprobeResult, FfprobeVideoSummary, Rendobar, output_data

VIDEO_URL = "https://cdn.rendobar.com/assets/examples/sample.mp4"
MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def main() -> None:
    # Reads RENDOBAR_API_KEY. RENDOBAR_API_URL is only for pointing the examples at another server.
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-quickstart") as rb:
        job = rb.jobs.run({"type": "ffprobe", "params": {"command": VIDEO_URL}})
        print(f"job {job.id}: {job.status}")
        if job.status != "complete":
            fail(f"status {job.status}")

        result = output_data(job, FfprobeResult)
        summary = result.summary
        if summary is None and MOCK:
            print("SKIP (mock: a synthesized job has no ffprobe summary)")
            return
        if not isinstance(summary, FfprobeVideoSummary):
            fail(f"expected a video summary, got {summary!r}")

        video, audio = summary.video, summary.audio
        print(f"duration: {summary.duration_sec} s")
        print(f"resolution: {video.width}x{video.height}")
        print(f"video codec: {video.codec}")
        print(f"audio codec: {audio.codec if audio is not None else 'none'}")
        if summary.duration_sec is None or summary.duration_sec <= 0:
            fail(f"duration {summary.duration_sec}")
        if not video.width or not video.height or not video.codec:
            fail(f"video stream {video!r}")


if __name__ == "__main__":
    main()

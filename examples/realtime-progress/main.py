"""Upload a local clip, start an ffmpeg job on it, and print the job's live events until it ends.

    pip install "rendobar[realtime]"
    RENDOBAR_API_KEY=rb_... python main.py

The events come over a WebSocket as they happen: progress (phase and fraction
done), log lines, steps, the machine the job runs on, and status changes. The
stream stops on its own after the job's final status. The clip is
`examples/fixtures/clip.mp4` (18 KB), uploaded as an ephemeral asset and
deleted at the end, also when a step fails.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, NoReturn, Optional

from rendobar import NotFoundError, Rendobar, realtime

CLIP = Path(__file__).resolve().parent.parent / "fixtures" / "clip.mp4"
PUBLIC_CLIP = "https://cdn.rendobar.com/assets/examples/sample.mp4"
MOCK = os.environ.get("RENDOBAR_EXAMPLES_MODE") == "mock"
COMMAND = "ffmpeg -i clip.mp4 -t 1 -vf scale=160:-2 -c:v libx264 -preset veryfast -c:a aac output.mp4"


def fail(what: str) -> NoReturn:
    raise SystemExit(f"FAIL: {what}")


def describe(event: realtime.RealtimeEvent) -> str:
    """One line per event. A type newer than this SDK arrives as an UnknownRealtimeEvent, never an error."""
    if isinstance(event, realtime.Connected):
        return "connected"
    if isinstance(event, realtime.JobProgress):
        done = "?" if event.progress is None else f"{event.progress:.0%}"
        return f"progress {event.phase or event.step}: {done}"
    if isinstance(event, realtime.JobLog):
        return f"log [{event.level}] {event.message}"
    if isinstance(event, realtime.JobStep):
        return f"step {event.step_name or event.step}: {event.status}"
    if isinstance(event, realtime.JobContext):
        return f"running on {event.machine}"
    if isinstance(event, realtime.JobStatusChanged):
        cost = f", {event.price_formatted}" if event.price_formatted else ""
        return f"status {event.status}{cost}"
    if isinstance(event, realtime.UnknownRealtimeEvent):
        return f"(an event this SDK does not know: {event.type})"
    return event.type


def follow(rb: Rendobar, job_id: str) -> Optional[realtime.JobStatusChanged]:
    """Print the job's events until it ends, and return its final status. None in mock mode (no WebSocket)."""
    seen: List[str] = []
    final: Optional[realtime.JobStatusChanged] = None
    try:
        for event in rb.realtime.subscribe_job(job_id, timeout=300):
            print(f"  {describe(event)}")
            seen.append(event.type)
            if isinstance(event, realtime.JobStatusChanged) and event.final:
                final = event
    except NotFoundError:
        if MOCK:  # the conformance mock serves HTTP only, so the handshake is a 404
            print("SKIP (mock: no websocket)")
            return None
        raise
    if not seen or seen[0] != "connected" or final is None:
        fail(f"the stream ended without a final status: {seen}")
    return final


def main() -> None:
    with Rendobar(base_url=os.environ.get("RENDOBAR_API_URL", "https://api.rendobar.com"), app="example-realtime-progress") as rb:
        asset_id = None if MOCK else rb.uploads.create(CLIP, content_type="video/mp4").id
        try:
            source = PUBLIC_CLIP if asset_id is None else f"asset://{asset_id}"
            created = rb.jobs.create({"type": "ffmpeg", "inputs": {"clip.mp4": source},
                                      "params": {"command": COMMAND, "timeout": 120}}, label="example realtime")
            print(f"job {created.id}: {created.status}")
            final = follow(rb, created.id)
            if final is None:
                return
            if final.status != "complete":
                fail(f"job {created.id} ended {final.status}: {final.error}")
            job = rb.jobs.get(created.id)  # the stream says it ended, the job holds the output
            print(f"job {job.id}: {job.status}")
            if job.status != "complete":
                fail(f"the stream said complete, the job says {job.status}")
        finally:
            if asset_id is not None:
                rb.assets.delete(asset_id)


if __name__ == "__main__":
    main()

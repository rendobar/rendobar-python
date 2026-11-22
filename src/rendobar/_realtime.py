"""`rb.realtime`: a workspace's events over the API's WebSocket, sync and asyncio.

The protocol, as the Go and TypeScript SDKs speak it:

- GET /events/ws (the workspace) or /events/ws/job/<id> (one job), upgraded to
  a WebSocket. The key goes in the Authorization header, never in the URL.
- The client's first message is `{"type": "init", "lastEventId": N}`. The hub
  replays the events it kept after N, sends `replay.done`, then live events.
- An event the hub keeps carries its cursor in `eventId`. A dropped connection
  reconnects with backoff (1 s, growing 1.5x to 30 s) and resumes after the last
  cursor, and an event seen before is skipped.
- A refused handshake that no retry fixes (a 4xx other than 408 and 429) raises.

The WebSocket library (`websockets`) is the `realtime` extra. It is imported
when a stream starts, so the rest of the SDK works without it. What is not I/O
(`_Stream`, `_Backoff`, `refused`) is shared; the async side only awaits.
"""
# pyright: strict, reportPrivateUsage=false
from __future__ import annotations

import asyncio
import importlib
import json
import random
import time
from typing import TYPE_CHECKING, AsyncGenerator, Dict, Generator, Mapping, Optional, Union

from ._errors import (
    InvalidArgumentError,
    RendobarError,
    api_key_error,
    client_closed,
    format_seconds,
    from_generated,
)
from ._generated.core.api_error import ApiError as _GeneratedApiError
from ._plumbing import path_segment, whole
from .realtime import Connected, RealtimeEvent, about_job, decode, ends_job

if TYPE_CHECKING:
    from ._async_client import AsyncRendobar
    from ._client import Rendobar

_EXTRA = 'rb.realtime needs the websockets package: pip install "rendobar[realtime]"'
# One message's size bound. A preview frame is up to 64 KB of base64, so 1 MiB is a technical ceiling, not a limit.
READ_LIMIT = 1 << 20
MIN_DELAY = 1.0  # seconds before the first reconnect
MAX_DELAY = 30.0
OPEN_TIMEOUT = 10.0  # seconds a handshake may take before it counts as a failed try


def require_websockets() -> None:
    """ImportError naming the extra when `websockets` is not installed. Called when a stream is asked for."""
    try:
        importlib.import_module("websockets")
    except ImportError as err:
        raise ImportError(_EXTRA) from err


def ws_url(base_url: str, path: str) -> str:
    """The API's base URL as a WebSocket URL: http becomes ws, https wss."""
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base + path


def refused(status: int, headers: Mapping[str, str], body: Union[bytes, bytearray]) -> RendobarError:
    """The API's error envelope from a refused handshake, as the error the same status raises on any other call."""
    decoded: object
    try:
        decoded = json.loads(bytes(body).decode("utf-8")) if body else None
    except ValueError:
        decoded = bytes(body).decode("utf-8", "replace")
    return from_generated(_GeneratedApiError(status_code=status, headers=dict(headers), body=decoded))


def permanent(err: RendobarError) -> bool:
    """A refusal reconnecting cannot fix: a 4xx other than 408 and 429."""
    status = err.status_code or 0
    return 400 <= status < 500 and status not in (408, 429)


def ended_early(job_id: str, timeout: float) -> RendobarError:
    return RendobarError(f"Job {job_id} did not end within {format_seconds(timeout)}. It may still finish: jobs.get() reads it.",
                         code="WAIT_TIMEOUT")


class _Backoff:
    """Seconds before the next reconnect: from 1 s, 1.5x per failed try, at most 30 s, with 10% jitter."""

    def __init__(self) -> None:
        self._delay = MIN_DELAY

    def reset(self) -> None:
        self._delay = MIN_DELAY  # a working connection starts the backoff over

    def next(self) -> float:
        pause = self._delay * (0.9 + 0.2 * random.random())
        self._delay = min(self._delay * 1.5, MAX_DELAY)
        return pause


class _Stream:
    """One stream's state across its connections: where to resume, which events to yield, when to stop."""

    def __init__(self, url: str, headers: Dict[str, str], *, last_event_id: int, job_id: Optional[str],
                 timeout: Optional[float]) -> None:
        self.url = url
        self.headers = headers
        self.last_event_id = last_event_id
        self.job_id = job_id
        self.timeout = timeout
        self.deadline = None if timeout is None else time.monotonic() + timeout
        self.backoff = _Backoff()

    def init(self) -> str:
        """The first message of a connection: resume after the last event yielded."""
        return json.dumps({"type": "init", "lastEventId": self.last_event_id})

    def take(self, frame: Union[str, bytes]) -> Optional[RealtimeEvent]:
        """The event to yield for `frame`, or None for a frame to skip: not text, not an event, seen before, or another job's."""
        if not isinstance(frame, str):
            return None
        decoded = decode(frame)
        if decoded is None:
            return None
        event, event_id = decoded
        if event_id:
            if event_id <= self.last_event_id:
                return None  # replayed again after a reconnect: already yielded
            self.last_event_id = event_id
        if self.job_id is not None and not about_job(event, self.job_id):
            return None
        return event

    def ends(self, event: RealtimeEvent) -> bool:
        return self.job_id is not None and ends_job(event, self.job_id)

    def remaining(self) -> Optional[float]:
        """Seconds left before `timeout`, or None without one."""
        return None if self.deadline is None else max(0.0, self.deadline - time.monotonic())

    def open_timeout(self) -> float:
        """Seconds a handshake may take: 10, or less when the deadline is nearer."""
        left = self.remaining()
        return OPEN_TIMEOUT if left is None else max(0.001, min(OPEN_TIMEOUT, left))

    def expired(self) -> Optional[RendobarError]:
        """The error to raise once `timeout` has passed, else None."""
        left = self.remaining()
        if left is None or left > 0 or self.job_id is None or self.timeout is None:
            return None
        return ended_early(self.job_id, self.timeout)

    def pause(self) -> float:
        """The backoff before reconnecting, cut short at the deadline."""
        delay = self.backoff.next()
        left = self.remaining()
        return delay if left is None else min(delay, left)


def _positive_seconds(name: str, value: object) -> None:
    """Checked at run time too: the type check is the caller's to run."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
        raise InvalidArgumentError(f"{name} must be a positive number of seconds. Got {value!r}.")


def _stream(api_key: Optional[str], base_url: str, headers: Dict[str, str], closed: bool, path: str, *,
            last_event_id: int, job_id: Optional[str], timeout: Optional[float]) -> _Stream:
    """Checks what can be checked before connecting, the same for both clients, and returns the stream's state."""
    if closed:
        raise client_closed()
    problem = api_key_error(api_key)
    if problem is not None:
        raise problem
    whole("last_event_id", last_event_id, 0)
    _positive_seconds("timeout", timeout)
    require_websockets()
    assert api_key is not None  # api_key_error refuses a missing key
    sent = dict(headers, Authorization=f"Bearer {api_key}")
    return _Stream(ws_url(base_url, path), sent, last_event_id=last_event_id, job_id=job_id, timeout=timeout)


class Realtime:
    """A workspace's events as they happen. Needs ``pip install "rendobar[realtime]"``.

    Each method returns a generator. Iterating it connects, reconnects on its
    own and resumes where it left off. Breaking out of the loop and dropping
    the generator closes the connection: wrap it in `contextlib.closing` to
    close it at a known point.
    """

    def __init__(self, client: Rendobar) -> None:
        self._client = client

    def connect(self, *, last_event_id: int = 0) -> Generator[RealtimeEvent, None, None]:
        """Every event of the workspace, until you stop iterating.

        Yields `Connected` on each connection, the events the workspace kept
        after `last_event_id` (all it keeps, from 0), `ReplayDone`, then live
        events. To resume in a later process, store the `event_id` of the last
        event you handled and pass it here. `Resync` says events were lost:
        read your state again.

        A refusal no reconnect fixes, such as a revoked key (401) or one without
        the `jobs:read` scope (403), raises its `RendobarError`.
        """
        client = self._client
        stream = _stream(client._api_key, client._base_url, client._headers, client._closed, "/events/ws",
                         last_event_id=last_event_id, job_id=None, timeout=None)
        return _sync_events(stream)

    def subscribe_job(self, job_id: str, *, timeout: Optional[float] = None) -> Generator[RealtimeEvent, None, None]:
        """One job's events, until it ends.

        Yields `Connected`, then the job's progress, steps, logs, resources,
        previews, status and result, replayed ones first, and stops after the
        `JobStatusChanged` whose `final` is True. A job that already ended stops
        after its replayed status. A job the workspace does not have raises
        `NotFoundError`. With `timeout` (seconds), a job that has not ended by
        then raises `RendobarError` with code `WAIT_TIMEOUT`.
        """
        safe = path_segment("job_id", job_id)
        client = self._client
        stream = _stream(client._api_key, client._base_url, client._headers, client._closed, f"/events/ws/job/{safe}",
                         last_event_id=0, job_id=safe, timeout=timeout)
        return _sync_events(stream)


def _sync_events(stream: _Stream) -> Generator[RealtimeEvent, None, None]:
    from websockets.exceptions import InvalidStatus, InvalidURI, WebSocketException
    from websockets.sync.client import connect

    while True:
        try:
            with connect(stream.url, additional_headers=stream.headers, max_size=READ_LIMIT,
                         open_timeout=stream.open_timeout()) as socket:
                socket.send(stream.init())
                stream.backoff.reset()
                yield Connected()
                while True:
                    event = stream.take(socket.recv(timeout=stream.remaining()))
                    if event is None:
                        continue
                    yield event
                    if stream.ends(event):
                        return
        except InvalidStatus as err:
            error = refused(err.response.status_code, err.response.headers, err.response.body or b"")
            if permanent(error):
                raise error from None
        except InvalidURI as err:
            raise InvalidArgumentError(f"base_url is not a URL the event stream can use: {err}") from None
        except (OSError, WebSocketException):
            pass  # the connection failed or dropped (a timeout is an OSError too): reconnect
        late = stream.expired()
        if late is not None:
            raise late
        time.sleep(stream.pause())
        late = stream.expired()
        if late is not None:
            raise late


class AsyncRealtime:
    """Same methods as `Rendobar.realtime`, as async generators: `async for event in rb.realtime.subscribe_job(id)`.

    Leaving the loop early leaves the connection open until the generator is
    closed: wrap it in `contextlib.aclosing` to close it at a known point.
    """

    def __init__(self, client: AsyncRendobar) -> None:
        self._client = client

    def connect(self, *, last_event_id: int = 0) -> AsyncGenerator[RealtimeEvent, None]:
        """Every event of the workspace, until you stop iterating. See `Realtime.connect`."""
        client = self._client
        stream = _stream(client._api_key, client._base_url, client._headers, client._closed, "/events/ws",
                         last_event_id=last_event_id, job_id=None, timeout=None)
        return _async_events(stream)

    def subscribe_job(self, job_id: str, *, timeout: Optional[float] = None) -> AsyncGenerator[RealtimeEvent, None]:
        """One job's events, until it ends. See `Realtime.subscribe_job`."""
        safe = path_segment("job_id", job_id)
        client = self._client
        stream = _stream(client._api_key, client._base_url, client._headers, client._closed, f"/events/ws/job/{safe}",
                         last_event_id=0, job_id=safe, timeout=timeout)
        return _async_events(stream)


async def _async_events(stream: _Stream) -> AsyncGenerator[RealtimeEvent, None]:
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus, InvalidURI, WebSocketException

    while True:
        try:
            async with connect(stream.url, additional_headers=stream.headers, max_size=READ_LIMIT,
                               open_timeout=stream.open_timeout()) as socket:
                await socket.send(stream.init())
                stream.backoff.reset()
                yield Connected()
                while True:
                    event = stream.take(await asyncio.wait_for(socket.recv(), stream.remaining()))
                    if event is None:
                        continue
                    yield event
                    if stream.ends(event):
                        return
        except InvalidStatus as err:
            error = refused(err.response.status_code, err.response.headers, err.response.body or b"")
            if permanent(error):
                raise error from None
        except InvalidURI as err:
            raise InvalidArgumentError(f"base_url is not a URL the event stream can use: {err}") from None
        except (OSError, asyncio.TimeoutError, WebSocketException):
            pass  # the connection failed or dropped: reconnect
        late = stream.expired()
        if late is not None:
            raise late
        await asyncio.sleep(stream.pause())
        late = stream.expired()
        if late is not None:
            raise late

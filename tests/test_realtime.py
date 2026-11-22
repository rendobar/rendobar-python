"""rb.realtime against a local WebSocket server that plays the API's event hub, sync and async.

Needs the realtime extra (websockets); skipped without it.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import threading
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple

import pytest

websockets = pytest.importorskip("websockets")
from websockets.sync.server import ServerConnection, serve  # noqa: E402

import rendobar._realtime  # noqa: E402
from rendobar import (  # noqa: E402
    AsyncRendobar,
    AuthenticationError,
    InvalidArgumentError,
    NotFoundError,
    PermissionDeniedError,
    Rendobar,
    RendobarError,
    realtime,
)

Serve = Callable[[ServerConnection, int, int], None]  # connection, its number (from 1), the lastEventId of its init
Refuse = Callable[[int], Optional[Tuple[int, str]]]  # handshake number -> (status, body) to refuse it, or None


class Hub:
    """The API's event socket. Records each handshake's path and headers and each init's lastEventId."""

    def __init__(self, serve_one: Serve, refuse: Optional[Refuse] = None) -> None:
        self.serve_one = serve_one
        self.refuse = refuse
        self.paths: List[str] = []
        self.headers: List[Dict[str, str]] = []
        self.inits: List[int] = []
        self._server = serve(self._handle, "127.0.0.1", 0, process_request=self._process)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self._server.socket.getsockname()[1]}"

    def _process(self, connection: ServerConnection, request: Any) -> Any:
        self.paths.append(request.path)
        self.headers.append({k.lower(): v for k, v in request.headers.raw_items()})
        refusal = self.refuse(len(self.paths)) if self.refuse else None
        if refusal is None:
            return None
        response = connection.respond(refusal[0], refusal[1])
        response.headers["X-Request-Id"] = "req_1"
        return response

    def _handle(self, connection: ServerConnection) -> None:
        init = json.loads(connection.recv())
        assert init["type"] == "init"
        self.inits.append(init["lastEventId"])
        self.serve_one(connection, len(self.inits), init["lastEventId"])

    def close(self) -> None:
        self._server.shutdown()


def send(connection: ServerConnection, *frames: str) -> None:
    for frame in frames:
        connection.send(frame)


def hold(connection: ServerConnection) -> None:
    """Keep the connection open until the client goes."""
    with contextlib.suppress(websockets.exceptions.ConnectionClosed):
        for _ in connection:
            pass


@pytest.fixture
def hub() -> Iterator[Callable[..., Hub]]:
    made: List[Hub] = []

    def make(serve_one: Serve, refuse: Optional[Refuse] = None) -> Hub:
        made.append(Hub(serve_one, refuse))
        return made[-1]

    yield make
    for one in made:
        one.close()


@pytest.fixture(autouse=True)
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendobar._realtime, "MIN_DELAY", 0.01)
    monkeypatch.setattr(rendobar._realtime, "MAX_DELAY", 0.02)


def take(events: Generator[realtime.RealtimeEvent, None, None], count: int) -> List[realtime.RealtimeEvent]:
    out: List[realtime.RealtimeEvent] = []
    with contextlib.closing(events):
        for event in events:
            out.append(event)
            if len(out) == count:
                break
    return out


async def take_async(make: Callable[[], Any], count: int) -> List[realtime.RealtimeEvent]:
    out: List[realtime.RealtimeEvent] = []
    stream = make()
    try:
        async for event in stream:
            out.append(event)
            if len(out) == count:
                break
    finally:
        await stream.aclose()
    return out


MODES = ["sync", "async"]


def collect(mode: str, url: str, count: int, *, job: Optional[str] = None, last_event_id: int = 0,
            timeout: Optional[float] = None) -> List[realtime.RealtimeEvent]:
    """`count` events (or all, for a job stream that ends) from the sync or the async client."""
    if mode == "sync":
        rb = Rendobar("rb_test", base_url=url)
        stream = rb.realtime.subscribe_job(job, timeout=timeout) if job else rb.realtime.connect(last_event_id=last_event_id)
        return take(stream, count)
    arb = AsyncRendobar("rb_test", base_url=url)

    def start() -> Any:
        return arb.realtime.subscribe_job(job, timeout=timeout) if job else arb.realtime.connect(last_event_id=last_event_id)

    return asyncio.run(asyncio.wait_for(take_async(start, count), 10))


EVERY_KIND = [
    '{"type":"job.created","jobId":"job_1","jobType":"ffmpeg","status":"waiting","eventId":8}',
    '{"type":"balance.updated","balance":9000000000000,"balanceFormatted":"$9000.00","timestamp":1763700000000,"eventId":9}',
    '{"type":"replay.done"}',
    '{"type":"job.progress","jobId":"job_1","timestamp":1763700000000,"progress":null,"phase":"processing","step":"ffmpeg",'
    '"metrics":{"fps":29.5,"speed":"1.2x"}}',
    '{"type":"job.metrics","jobId":"job_1","timestamp":1,"cpuCores":2,"memUsedMB":100,"gpuPct":null}',
    '{"type":"notification","id":10,"severity":"warning","title":"t","message":"m"}',
    '{"type":"member.updated","userId":"u_1","role":null,"reason":"left","timestamp":1,"eventId":11}',
    'not json',
    '{"type":"job.teleported","jobId":"job_1","eventId":12}',
    '{"type":"job.log","jobId":"job_1","level":3,"message":"m"}',
    '{"type":"resync","reason":"buffer_overflow"}',
]


@pytest.mark.parametrize("mode", MODES)
def test_every_kind_is_read_and_the_rest_is_tolerated(mode: str, hub: Callable[..., Hub]) -> None:
    def serve_one(connection: ServerConnection, n: int, last: int) -> None:
        send(connection, *EVERY_KIND)
        hold(connection)

    server = hub(serve_one)
    got = collect(mode, server.url, 11, last_event_id=7)
    assert server.inits == [7]
    assert server.paths == ["/events/ws"]
    headers = server.headers[0]
    assert headers["authorization"] == "Bearer rb_test" and headers["x-rendobar-client"].startswith("python/")
    assert isinstance(got[0], realtime.Connected)
    created = got[1]
    assert isinstance(created, realtime.JobCreated) and created.job_id == "job_1" and created.job_type == "ffmpeg"
    assert created.event_id == 8
    balance = got[2]
    assert isinstance(balance, realtime.BalanceUpdated) and balance.balance == 9_000_000_000_000 and balance.timestamp
    assert isinstance(got[3], realtime.ReplayDone)
    progress = got[4]
    assert isinstance(progress, realtime.JobProgress) and progress.progress is None and progress.phase == "processing"
    assert progress.metrics == {"fps": 29.5, "speed": "1.2x"} and progress.event_id == 0
    resources = got[5]
    assert isinstance(resources, realtime.JobResources) and resources.type == "job.resources"
    assert resources.cpu_cores == 2 and resources.mem_used_mb == 100 and resources.gpu_pct is None
    notification = got[6]  # an older hub's numeric id is the cursor; a notification's own id is a string
    assert isinstance(notification, realtime.Notification) and notification.event_id == 10 and notification.id is None
    member = got[7]
    assert isinstance(member, realtime.MemberUpdated) and member.role is None and member.reason == "left"
    newer = got[8]
    assert isinstance(newer, realtime.UnknownRealtimeEvent) and newer.type == "job.teleported" and newer.event_id == 12
    assert newer.job_id == "job_1" and newer.raw["eventId"] == 12
    reshaped = got[9]  # a known type whose fields changed shape
    assert isinstance(reshaped, realtime.UnknownRealtimeEvent) and reshaped.type == "job.log"
    resync = got[10]
    assert isinstance(resync, realtime.Resync) and resync.reason == "buffer_overflow"


@pytest.mark.parametrize("mode", MODES)
def test_a_dropped_stream_reconnects_and_resumes_after_the_last_event(mode: str, hub: Callable[..., Hub]) -> None:
    def serve_one(connection: ServerConnection, n: int, last: int) -> None:
        if n == 1:
            send(connection, '{"type":"job.result","jobId":"job_1","eventId":1}', '{"type":"job.result","jobId":"job_2","eventId":2}')
            connection.close()  # the connection drops
            return
        send(connection, '{"type":"job.result","jobId":"job_2","eventId":2}', '{"type":"job.result","jobId":"job_3","eventId":3}')
        hold(connection)

    server = hub(serve_one)
    got = collect(mode, server.url, 5)
    assert [type(e).__name__ for e in got] == ["Connected", "JobResult", "JobResult", "Connected", "JobResult"]
    assert [e.job_id for e in got if isinstance(e, realtime.JobResult)] == ["job_1", "job_2", "job_3"]
    assert server.inits == [0, 2]


@pytest.mark.parametrize("mode", MODES)
def test_a_job_stream_ends_on_its_final_status(mode: str, hub: Callable[..., Hub]) -> None:
    def serve_one(connection: ServerConnection, n: int, last: int) -> None:
        send(connection,
             '{"type":"balance.updated","balance":5,"eventId":1}',
             '{"type":"job.status","jobId":"job_2","status":"complete","eventId":2}',
             '{"type":"replay.done"}',
             '{"type":"job.status","jobId":"job_1","status":"running"}',
             '{"type":"job.log","jobId":"job_1","level":"info","message":"go"}',
             '{"type":"job.status","jobId":"job_1","status":"complete","price":1500000}',
             '{"type":"job.log","jobId":"job_1","level":"info","message":"after the end"}')
        hold(connection)

    server = hub(serve_one)
    got = collect(mode, server.url, 100, job="job_1")
    assert server.paths == ["/events/ws/job/job_1"]
    # The workspace's other events, another job's end among them, are left out.
    assert [e.type for e in got] == ["connected", "job.status", "job.log", "job.status"]
    final = got[-1]
    assert isinstance(final, realtime.JobStatusChanged) and final.final and final.price == 1_500_000


@pytest.mark.parametrize("mode", MODES)
def test_a_refusal_raises_its_error_without_retrying(mode: str, hub: Callable[..., Hub]) -> None:
    body = json.dumps({"error": {"code": "INSUFFICIENT_SCOPE", "message": "needs jobs:read"}})
    server = hub(lambda c, n, last: hold(c), lambda n: (403, body))
    with pytest.raises(PermissionDeniedError) as info:
        collect(mode, server.url, 1)
    assert info.value.code == "INSUFFICIENT_SCOPE" and info.value.status_code == 403 and info.value.request_id == "req_1"
    assert len(server.paths) == 1


@pytest.mark.parametrize("mode", MODES)
def test_a_job_the_workspace_does_not_have_is_not_found(mode: str, hub: Callable[..., Hub]) -> None:
    body = json.dumps({"error": {"code": "NOT_FOUND", "message": 'Job "job_x" not found'}})
    server = hub(lambda c, n, last: hold(c), lambda n: (404, body))
    with pytest.raises(NotFoundError):
        collect(mode, server.url, 1, job="job_x")


@pytest.mark.parametrize("mode", MODES)
def test_a_server_error_is_retried(mode: str, hub: Callable[..., Hub]) -> None:
    server = hub(lambda c, n, last: hold(c), lambda n: (503, "") if n < 3 else None)
    got = collect(mode, server.url, 1)
    assert isinstance(got[0], realtime.Connected) and len(server.paths) == 3


@pytest.mark.parametrize("mode", MODES)
def test_a_job_that_does_not_end_in_time_raises_wait_timeout(mode: str, hub: Callable[..., Hub]) -> None:
    def serve_one(connection: ServerConnection, n: int, last: int) -> None:
        send(connection, '{"type":"job.status","jobId":"job_1","status":"running"}')
        hold(connection)

    server = hub(serve_one)
    with pytest.raises(RendobarError) as info:
        collect(mode, server.url, 100, job="job_1", timeout=0.3)
    assert info.value.code == "WAIT_TIMEOUT"


@pytest.mark.parametrize("mode", MODES)
def test_bad_keys_and_ids_fail_before_connecting(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDOBAR_API_KEY", raising=False)
    client: Any = Rendobar if mode == "sync" else AsyncRendobar
    with pytest.raises(AuthenticationError) as missing:
        client(base_url="http://127.0.0.1:1").realtime.connect()
    assert missing.value.code == "MISSING_API_KEY"
    with pytest.raises(AuthenticationError) as invalid:
        client("sk_x", base_url="http://127.0.0.1:1").realtime.subscribe_job("job_1")
    assert invalid.value.code == "INVALID_API_KEY"
    for bad in ("../x", "", "a/b"):
        with pytest.raises(InvalidArgumentError):
            client("rb_x").realtime.subscribe_job(bad)
    with pytest.raises(InvalidArgumentError):
        client("rb_x").realtime.connect(last_event_id=-1)
    with pytest.raises(InvalidArgumentError):
        client("rb_x").realtime.subscribe_job("job_1", timeout=0)


def test_without_the_extra_the_error_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "websockets", None)  # import websockets now raises ImportError
    with pytest.raises(ImportError, match=r'pip install "rendobar\[realtime\]"'):
        Rendobar("rb_x").realtime.subscribe_job("job_1")
    # The base package and the event types work without it.
    assert realtime.decode('{"type":"job.result","jobId":"job_1"}') is not None


def test_a_closed_client_refuses_a_stream() -> None:
    rb = Rendobar("rb_x")
    rb.close()
    with pytest.raises(RendobarError) as info:
        rb.realtime.connect()
    assert info.value.code == "CLIENT_CLOSED"

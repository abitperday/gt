import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

import web
from src.schema.telemetry import TelemetryStat
from src.services.live_telemetry import LiveTelemetryHub


def packet(packet_id: int, lap: int, distance: float, x: float) -> TelemetryStat:
    return TelemetryStat(
        package_id=packet_id,
        current_lap=lap,
        current_gear=3,
        suggested_gear=3,
        speed=100,
        total_laps=5,
        current_position=1,
        total_racers=2,
        rpm=5000,
        throttle_rate=70,
        brake_rate=0,
        x=x,
        y=0,
        z=0,
        time_on_track=0,
        lap_distance=distance,
        best_lap=0,
        last_lap=90_000,
        in_race=True,
        car_id=123,
        received_at=time.time(),
    )


def run_stream(monkeypatch, hub, updates, during_sleep=()):
    """Advance the producer deterministically at the stream's coalescing points."""
    sent = []
    updates = iter(updates)
    during_sleep = iter(during_sleep)
    full_snapshots = []
    original_snapshot = hub.snapshot

    def snapshot(*, include_track=False):
        if include_track:
            full_snapshots.append(True)
        return original_snapshot(include_track=include_track)

    async def to_thread(function, *args):
        update = next(updates, None)
        if update is None:
            raise WebSocketDisconnect()
        update()
        return function(*args)

    async def sleep(_seconds):
        update = next(during_sleep, None)
        if update is not None:
            update()

    class Socket:
        app = SimpleNamespace(state=SimpleNamespace(live_hub=hub))

        async def accept(self):
            pass

        async def send_json(self, data):
            sent.append(data)

    monkeypatch.setattr(hub, "snapshot", snapshot)
    monkeypatch.setattr(web.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(web.asyncio, "sleep", sleep)
    asyncio.run(web.live_telemetry(Socket()))
    assert hub.client_count == 0
    return [item["frame"] for item in sent if item["type"] == "frame"], len(full_snapshots)


@pytest.mark.parametrize("lost_during_sleep", [False, True])
def test_completed_trace_survives_latest_only_coalescing(monkeypatch, lost_during_sleep):
    # Freeze the cadence so only the completion packet contains a full trace.
    monkeypatch.setattr(web.time, "monotonic", lambda: 1000.0)
    hub = LiveTelemetryHub()
    hub.publish(packet(1, 1, 0, 0))
    hub.publish(packet(2, 1, 10, 10))

    def complete_lap():
        hub.publish(packet(3, 2, 0, 0))
        assert hub.snapshot()[1].track_trace is not None
        if not lost_during_sleep:
            replace_completion()

    def replace_completion():
        hub.publish(packet(4, 2, 2, 2))
        assert hub.snapshot()[1].track_trace is None

    frames, full_snapshots = run_stream(
        monkeypatch,
        hub,
        [complete_lap, lambda: hub.publish(packet(5, 2, 4, 4))],
        [replace_completion] if lost_during_sleep else [],
    )

    assert frames[0]["track_ready"] is False
    assert frames[1]["packet_id"] == 4  # Keep the newest vehicle position.
    assert frames[1]["track_ready"] is True
    assert frames[1]["track_trace"] == [[0, 0], [10, 0], [0, 0]]
    assert frames[2]["packet_id"] == 5
    assert frames[2]["track_trace"] is None
    assert full_snapshots == 2  # Reconnect snapshot plus one completion recovery.


def test_reconnected_dashboard_receives_retained_completed_trace(monkeypatch):
    monkeypatch.setattr(web.time, "monotonic", lambda: 1000.0)
    hub = LiveTelemetryHub()
    hub.publish(packet(1, 1, 0, 0))
    hub.publish(packet(2, 1, 10, 10))
    hub.publish(packet(3, 2, 0, 0))
    hub.publish(packet(4, 2, 2, 2))
    assert hub.snapshot()[1].track_trace is None

    frames, full_snapshots = run_stream(
        monkeypatch, hub, [lambda: hub.publish(packet(5, 2, 4, 4))]
    )

    assert frames[0]["track_ready"] is True
    assert frames[0]["track_trace"] == [[0, 0], [10, 0], [0, 0]]
    assert frames[1]["track_trace"] is None
    assert full_snapshots == 1


def test_new_session_recovers_its_own_completed_trace(monkeypatch):
    monkeypatch.setattr(web.time, "monotonic", lambda: 1000.0)
    hub = LiveTelemetryHub()
    hub.publish(packet(1, 1, 0, 0))
    hub.publish(packet(2, 1, 10, 10))
    hub.publish(packet(3, 2, 0, 0))

    def complete_new_session():
        hub.publish(packet(4, 1, 0, 100))
        hub.publish(packet(5, 1, 10, 110))
        hub.publish(packet(6, 2, 0, 100))
        hub.publish(packet(7, 2, 2, 102))
        assert hub.snapshot()[1].track_trace is None

    frames, full_snapshots = run_stream(monkeypatch, hub, [complete_new_session])

    assert frames[0]["session_id"] == 1
    assert frames[1]["session_id"] == 2
    assert frames[1]["track_trace"] == [[100, 0], [110, 0], [100, 0]]
    assert full_snapshots == 2

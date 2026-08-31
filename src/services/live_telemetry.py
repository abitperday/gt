import math
import threading
import time

from pydantic import BaseModel

from src.schema.telemetry import TelemetryStat


def _finite(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    return value if math.isfinite(value) else None


class LiveFrame(BaseModel):
    """Stable, browser-facing subset of one GT7 telemetry packet."""

    packet_id: int
    captured_at: float
    car_id: int
    speed_kmh: int
    gear: int
    suggested_gear: int
    rpm: float
    rpm_warning: int | None
    rpm_limiter: int | None
    throttle_pct: int
    brake_pct: int
    lap: int
    total_laps: int
    position: int
    total_racers: int
    best_lap_ms: int | None
    last_lap_ms: int | None
    lap_distance_m: float
    fuel_l: float | None
    fuel_capacity_l: float | None
    boost: float | None
    oil_pressure: float | None
    oil_temp_c: float | None
    water_temp_c: float | None
    tyre_temp_fl_c: float | None
    tyre_temp_fr_c: float | None
    tyre_temp_rl_c: float | None
    tyre_temp_rr_c: float | None
    tyre_slip_fl: float | None
    tyre_slip_fr: float | None
    tyre_slip_rl: float | None
    tyre_slip_rr: float | None
    in_race: bool
    paused: bool

    @classmethod
    def from_telemetry(cls, event: TelemetryStat) -> "LiveFrame":
        return cls(
            packet_id=event.package_id,
            captured_at=event.received_at or time.time(),
            car_id=event.car_id,
            speed_kmh=max(0, event.speed),
            gear=event.current_gear,
            suggested_gear=event.suggested_gear,
            rpm=float(_finite(event.rpm) or 0),
            rpm_warning=event.rpm_rev_warning,
            rpm_limiter=event.rpm_rev_limiter,
            throttle_pct=max(0, min(100, event.throttle_rate)),
            brake_pct=max(0, min(100, event.brake_rate)),
            lap=event.current_lap,
            total_laps=event.total_laps,
            position=event.current_position,
            total_racers=event.total_racers,
            best_lap_ms=event.best_lap if event.best_lap > 0 else None,
            last_lap_ms=event.last_lap if event.last_lap > 0 else None,
            lap_distance_m=float(_finite(event.lap_distance) or 0),
            fuel_l=_finite(event.fuel_current),
            fuel_capacity_l=_finite(event.fuel_capacity),
            boost=_finite(event.boost),
            oil_pressure=_finite(event.oil_pressure),
            oil_temp_c=_finite(event.oil_temp),
            water_temp_c=_finite(event.water_temp),
            tyre_temp_fl_c=_finite(event.tyre_temp_fl),
            tyre_temp_fr_c=_finite(event.tyre_temp_fr),
            tyre_temp_rl_c=_finite(event.tyre_temp_rl),
            tyre_temp_rr_c=_finite(event.tyre_temp_rr),
            tyre_slip_fl=_finite(event.tyre_slip_fl),
            tyre_slip_fr=_finite(event.tyre_slip_fr),
            tyre_slip_rl=_finite(event.tyre_slip_rl),
            tyre_slip_rr=_finite(event.tyre_slip_rr),
            in_race=event.in_race,
            paused=event.is_paused,
        )


class LiveTelemetryHub:
    """Thread-safe latest-frame broadcaster with no per-client backlog."""

    def __init__(self):
        self._condition = threading.Condition()
        self._latest: LiveFrame | None = None
        self._sequence = 0
        self._clients = 0

    def publish(self, event: TelemetryStat | LiveFrame) -> int:
        frame = (
            event if isinstance(event, LiveFrame) else LiveFrame.from_telemetry(event)
        )
        with self._condition:
            self._latest = frame
            self._sequence += 1
            sequence = self._sequence
            self._condition.notify_all()
            return sequence

    def snapshot(self) -> tuple[int, LiveFrame] | None:
        with self._condition:
            if self._latest is None:
                return None
            return self._sequence, self._latest

    def wait_for_update(
        self, after_sequence: int, timeout: float
    ) -> tuple[int, LiveFrame] | None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._sequence > after_sequence, timeout=max(0, timeout)
            )
            if self._latest is None or self._sequence <= after_sequence:
                return None
            return self._sequence, self._latest

    def connect(self) -> int:
        with self._condition:
            self._clients += 1
            return self._clients

    def disconnect(self) -> int:
        with self._condition:
            self._clients = max(0, self._clients - 1)
            return self._clients

    @property
    def client_count(self) -> int:
        with self._condition:
            return self._clients

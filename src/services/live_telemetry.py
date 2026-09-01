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
    delta_to_reference_ms: float | None
    last_lap_delta_ms: float | None
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
    lights_active: bool
    high_beams: bool
    low_beams: bool

    @classmethod
    def from_telemetry(cls, event: TelemetryStat, delta_to_reference_ms: float | None = None, last_lap_delta_ms: float | None = None) -> "LiveFrame":
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
            delta_to_reference_ms=delta_to_reference_ms,
            last_lap_delta_ms=last_lap_delta_ms,
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
            lights_active=event.lights_active,
            high_beams=event.high_beams,
            low_beams=event.low_beams,
        )


class LiveTelemetryHub:
    """Thread-safe latest-frame broadcaster with no per-client backlog."""

    def __init__(self):
        self._condition = threading.Condition()
        self._latest: LiveFrame | None = None
        self._sequence = 0
        self._clients = 0
        self._active_lap: int | None = None
        self._lap_started_at: float | None = None
        self._active_samples: list[tuple[float, float]] = []
        self._reference_lap: list[tuple[float, float]] | None = None
        self._reference_lap_time: float | None = None
        self._best_lap_seen: int | None = None
        self._last_lap_delta_ms: float | None = None

    def _reference_elapsed(self, distance: float) -> float | None:
        samples = self._reference_lap
        if not samples or len(samples) < 2:
            return None
        if distance < samples[0][0] or distance > samples[-1][0]:
            return None
        for (d0, t0), (d1, t1) in zip(samples, samples[1:]):
            if d0 <= distance <= d1 and d1 > d0:
                ratio = (distance - d0) / (d1 - d0)
                return t0 + ratio * (t1 - t0)
        return samples[-1][1]

    def _lap_delta(self, event: TelemetryStat) -> float | None:
        if event.current_lap <= 0 or (self._active_lap is not None and event.current_lap < self._active_lap):
            self._active_lap = None
            self._lap_started_at = None
            self._active_samples = []
            self._reference_lap = None
            self._reference_lap_time = None
            self._best_lap_seen = None
            self._last_lap_delta_ms = None
            return None
        if self._active_lap != event.current_lap:
            if self._active_lap is not None and event.last_lap > 0 and self._best_lap_seen and self._best_lap_seen > 0 and event.last_lap != self._best_lap_seen:
                self._last_lap_delta_ms = event.last_lap - self._best_lap_seen
            if self._active_lap is not None and event.last_lap > 0:
                self._best_lap_seen = event.last_lap if self._best_lap_seen is None else min(self._best_lap_seen, event.last_lap)
            if len(self._active_samples) >= 2:
                lap_time = self._active_samples[-1][1]
                if self._reference_lap_time is None or lap_time < self._reference_lap_time:
                    self._reference_lap = self._active_samples
                    self._reference_lap_time = lap_time
            self._active_lap = event.current_lap
            self._lap_started_at = event.received_at or time.time()
            self._active_samples = []
        started = self._lap_started_at
        if started is None or event.current_lap <= 0:
            return None
        elapsed_ms = max(0.0, ((event.received_at or time.time()) - started) * 1000)
        distance = float(event.lap_distance)
        if not self._active_samples or distance >= self._active_samples[-1][0]:
            self._active_samples.append((distance, elapsed_ms))
        reference_ms = self._reference_elapsed(distance)
        return None if reference_ms is None else elapsed_ms - reference_ms

    def publish(self, event: TelemetryStat | LiveFrame) -> int:
        frame = event if isinstance(event, LiveFrame) else LiveFrame.from_telemetry(event, self._lap_delta(event), self._last_lap_delta_ms)
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

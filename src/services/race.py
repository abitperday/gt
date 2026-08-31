import enum
from typing import Optional

from src.schema.telemetry import TelemetryStat
from src.services.lap import LapTracker
from src.storage import Storage


class RaceType(enum.Enum):
    RACE = 0
    TIME_TRIAL = 1
    REPLAY = 2


class RaceTracker:
    def __init__(self, race_type: RaceType, wait_for_next_lap: bool = False):
        print("RACE STARTED", race_type)
        self.max_speed = -1
        self.cur_lap_idx = -1
        self.laps: list[LapTracker] = []
        self.car_id: Optional[int] = None
        self.special_packet_time = 0.0

        self._prev_event: Optional[TelemetryStat] = None
        self._best_lap: Optional[int] = None
        self.race_type = race_type

        # Workaround for recording telemetry from a replay.
        self._wait_for_next_lap = wait_for_next_lap

    def is_waiting(self):
        return self._wait_for_next_lap

    def _is_new_lap(self, event: TelemetryStat) -> bool:
        if event.current_lap <= 0:
            return False

        # Time trials do not include total_laps.
        # Demonstrations have in_race != true.
        # These modes need to be distinguished.

        """
            Race:
                in_race: true
                total_laps is available (endurance races still need checking)

                Start: current_lap = 1 (prev_lap = 0)
                Race end: current_lap > total_laps
            Time trial:
                in_race: true
                current_position: -1
                total_laps: -1

                First lap starts: current_lap = 1 (prev_lap = 0)
                End: in_race: false; the final lap is excluded
            Replay (qualifying or time trial):
                in_race: false
                current_position: 1
                total_laps: 1

                Lap start: current_lap = 1 (prev_lap = 0)
                End: current_lap = 2
            Demonstration (license center or circuit experience):
                Not implemented yet

            Known issue when
        """

        if self._prev_event is None and event.current_lap > 0:
            # Workaround for recording telemetry from a replay.
            if self._wait_for_next_lap:
                return False

            return True

        if self._prev_event and event.current_lap > self._prev_event.current_lap:
            # Workaround for recording telemetry from a replay.
            if self._wait_for_next_lap:
                self._wait_for_next_lap = False

            return True

        return False

    def process_event(self, event: TelemetryStat):
        if self.car_id is None:
            self.car_id = event.car_id

        if len(self.laps) == 0:
            self.special_packet_time = 0

        if self._is_new_lap(event):
            self.special_packet_time += event.last_lap - len(self.laps) * 1000 / 60
            if self.laps:
                self.laps[-1].finish(event.last_lap)

            self.laps.append(LapTracker())

        if event.current_lap > 0 and self.laps:
            self.laps[-1].process_event(event)

        self._prev_event = event

    def _save_dump(self, db: Storage):
        assert self._best_lap is not None

        assert self.car_id is not None
        race_id, race_folder = db.create_session(
            car_id=self.car_id, best_lap_time=self._best_lap
        )

        for i, lap in enumerate(self.laps):
            lap.dump(race_folder, i + 1)
            db.save_lap(i + 1, race_id, lap.lap_time())

        print(f"RACE {race_id} saved")

    def finish(self, db: Storage, event: TelemetryStat):
        if self.race_type == RaceType.TIME_TRIAL:
            if self.laps:
                self.laps.pop()
        elif self.laps:
            self.laps[-1].finish(event.last_lap)

        # GT7 can emit a terminal race packet immediately after leaving a menu or
        # reconnecting. There is nothing trustworthy to persist until at least one
        # lap has actually been accumulated.
        if not self.laps:
            print("RACE discarded: no captured laps")
            return None

        self._best_lap = event.best_lap
        return self._save_dump(db)

from typing import Optional

from src.schema.telemetry import TelemetryStat
from src.services.live_telemetry import LiveTelemetryHub
from src.services.race import RaceTracker, RaceType
from src.storage import Storage


class Tracker:
    def __init__(
        self, db: Storage, debug: bool = False, live_hub: LiveTelemetryHub | None = None
    ):
        self.is_race_running = False
        self.race_tracker: Optional[RaceTracker] = None
        self.prev_event: Optional[TelemetryStat] = None
        self._db = db
        self._debug = debug
        self._live_hub = live_hub

        self.all_events: list[TelemetryStat] = []
        self._current_race_type: Optional[RaceType] = None

        # Workaround
        self._waiting_replay_start_lap = False

    def _is_race_finished(self, event: TelemetryStat) -> bool:
        # Workaround for recording telemetry from a replay.
        assert self.race_tracker
        if self.race_tracker.is_waiting():
            return False

        if not self.prev_event:
            return False

        if (
            self._current_race_type == RaceType.RACE
            and event.current_lap > event.total_laps
        ):
            return True

        if self._current_race_type == RaceType.TIME_TRIAL and not event.in_race:
            return True

        if (
            self._current_race_type == RaceType.REPLAY
            and event.current_lap > self.prev_event.current_lap
            and self.prev_event.current_lap > 0
        ):
            return True

        return False

    def process_event(self, d_event: bytes):
        event = TelemetryStat.from_bytes(d_event, self.prev_event)
        if event:
            if self._live_hub is not None:
                self._live_hub.publish(event)
            self._process_parsed_event(event)

    def _is_race_started(self, event: TelemetryStat):
        return event.current_lap > 0 and (
            self.prev_event is None or self.prev_event.current_lap <= 0
        )

    def _get_race_type(self, event: TelemetryStat) -> Optional[RaceType]:
        if (
            not event.in_race
            and event.current_position == 1
            and event.total_racers == 1
        ):
            return RaceType.REPLAY

        if event.in_race and event.total_laps == 0:
            return RaceType.TIME_TRIAL

        if event.total_laps:
            return RaceType.RACE

        # Handles events that look like a lap start but are not.
        return None

    # for tests
    def _process_parsed_event(self, event: TelemetryStat):
        if self._debug:
            self.all_events.append(event)

        if self.race_tracker is None:
            ### Check start race
            """
            In replay mode it may be:
                current_lap > 1
                prev_event.current_lap < 0
            Example in the eidger.gtdata test fixture:
            (The lap starts with current_lap=3 and prev_event.current_lap=-1.)
            """
            if self._is_race_started(event):
                ### RACE STARTED
                self._current_race_type = self._get_race_type(event)
                if self._current_race_type:
                    if (
                        self._current_race_type == RaceType.REPLAY
                        and event.current_lap > 1
                    ):
                        self.race_tracker = RaceTracker(
                            self._current_race_type, wait_for_next_lap=True
                        )
                    else:
                        self.race_tracker = RaceTracker(self._current_race_type)

        if not self.race_tracker:
            self.prev_event = event
            return

        if self._is_race_finished(event):
            self.race_tracker.finish(self._db, event)
            self.race_tracker = None
            self._current_race_type = None
            self.prev_event = event

            if self._debug:
                with open("dump.gtdata", "w") as f:
                    f.writelines([f"{x.model_dump_json()}\n" for x in self.all_events])
                self.all_events = []
            return

        self.race_tracker.process_event(event)

        self.prev_event = event

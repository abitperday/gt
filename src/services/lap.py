import pandas as pd

from src.schema.telemetry import TelemetryStat


class LapTracker:
    def __init__(self):
        self.stats: list[TelemetryStat] = []
        self._lap_time = None

    def process_event(self, event: TelemetryStat):
        self.stats.append(event)

    def finish(self, lap_time: int):
        """
        !!!TODO!!!
        # Adapted from https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728/post-13810797
        self.current_lap.lap_live_time = (self.current_lap.lap_ticks * 1. / 60.) - (self.session.special_packet_time / 1000.)
        """
        self._lap_time = lap_time

    def lap_time(self):
        return self._lap_time

    def dump(self, dirname: str, idx: int):
        lap_label = f"lap_{idx}"
        df = pd.DataFrame(
            [
                (
                    item.current_gear,
                    item.speed,
                    item.rpm,
                    item.throttle_rate,
                    item.brake_rate,
                    item.x,
                    item.y,
                    item.z,
                    item.lap_distance,
                )
                for item in self.stats
            ],
            columns=[
                "gear",
                "speed",
                "rpm",
                "throttle",
                "brake",
                "x",
                "y",
                "z",
                "dist",
            ],
        )
        df.to_csv(f"{dirname}/{lap_label}.csv", index=False)

import os
import shutil

import pytest
from sqlmodel import SQLModel

from src.domain.models import Lap
from src.schema.telemetry import TelemetryStat
from src.services.tracker import Tracker
from src.storage import Storage

TEST_STORAGE_DIR = ".test"


class FakeEventStreamer:
    def __init__(self, dump_path: str):
        self.data = []
        with open(dump_path, "r") as f:
            for line in f:
                self.data.append(TelemetryStat.model_validate_json(line.strip()))

    def stream_events(self):
        for item in self.data:
            yield item


@pytest.fixture(autouse=True)
def fake_storage():
    os.makedirs(TEST_STORAGE_DIR)
    yield
    # If tests fail,
    shutil.rmtree(TEST_STORAGE_DIR)


@pytest.mark.parametrize(
    "dump_path, lap_times",
    [
        (["./tests/fixtures/race__tsukuba.gtdata", [57730, 58603, 63024]]),
        (
            [
                "./tests/fixtures/time_trial__atalanta.gtdata",
                [75665, 81072, 73487, 80223, 72988, 73533, 76490, 87682],
            ]
        ),
        (["./tests/fixtures/replay__atalanta.gtdata", [66640]]),
        (["./tests/fixtures/replay__eidger.gtdata", [76454]]),
        (["./tests/fixtures/replay__nurburg__strange.gtdata", [145343]]),
    ],
)
def test_lap_times(dump_path, lap_times):
    db = Storage(TEST_STORAGE_DIR)
    SQLModel.metadata.create_all(db.engine)

    tracker = Tracker(db=db)

    receiver = FakeEventStreamer(dump_path)
    for event in receiver.stream_events():
        tracker._process_parsed_event(event)

    laps = db.get_all_laps()
    assert len(laps) == len(lap_times)
    for i, lap in enumerate(laps):
        assert lap.time == lap_times[i]

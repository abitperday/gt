import os
import shutil
import sqlite3
import time
from datetime import datetime
from uuid import uuid4

from sqlmodel import Session, create_engine, select

from src.domain.models import Lap, Race


class Storage:
    def __init__(self, storage_dir: str = ".run", verbose: bool = False):
        self._verbose = verbose
        self._storage_dir = storage_dir

        self._log("Initializing storage")

        """
        Store telemetry at:
        {storage_dir}/storage/_data/{session_id}/{lap_number}.csv
        """

        self.engine = create_engine(f"sqlite:///{self._storage_dir}/storage/db.sqlite")

        os.makedirs(f"{self._storage_dir}/storage/_data", exist_ok=True)
        self.db = sqlite3.connect(f"{self._storage_dir}/storage/db.sqlite")

        self._log("Storage created")

    def create_session(self, car_id: int, best_lap_time: int) -> tuple[str, str]:
        session_id = uuid4().hex

        with Session(self.engine) as db:
            race = Race(
                id=session_id,
                car_id=car_id,
                best_lap_time=best_lap_time,
                end_ts=int(time.time()),
            )
            db.add(race)
            db.commit()

        session_folder = f"{self._storage_dir}/storage/_data/{session_id}"
        os.makedirs(session_folder, exist_ok=True)
        self._log(f"Session {session_id} saved")
        return session_id, session_folder

    def save_lap(self, lap_number: int, race_id: str, lap_time: int):
        lap_id = uuid4().hex
        with Session(self.engine) as db:
            lap = Lap(
                id=lap_id,
                number=lap_number,
                race_id=race_id,
                time=lap_time,
            )
            db.add(lap)
            db.commit()

    def _log(self, msg: str):
        if self._verbose:
            print(f"[{datetime.now()}] {msg}")

    def _clear(self):
        shutil.rmtree(self._storage_dir)

    def __enter__(self): ...

    def __exit__(self): ...

    def get_all_laps(self):
        with Session(self.engine) as db:
            query = select(Lap)
            res = db.exec(query)
            laps = res.all()

        return laps

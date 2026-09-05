import asyncio
import time
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, asc, col, create_engine, desc, select

from src.domain.models import Car, Lap, Race, Track
from src.services.lap_comparison import ComparisonError, compare_laps
from src.services.live_telemetry import LiveTelemetryHub

PROJECT_ROOT = Path(__file__).resolve().parent
STORAGE_DIR = PROJECT_ROOT / ".run" / "storage"
DATA_DIR = STORAGE_DIR / "_data"
DATABASE_PATH = STORAGE_DIR / "db.sqlite"
db_url = f"sqlite:///{DATABASE_PATH}"
connect_args = {"check_same_thread": False}
engine = create_engine(db_url, connect_args=connect_args)


def get_db():
    with Session(engine) as session:
        yield session


app = FastAPI()
app.state.live_hub = LiveTelemetryHub()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecordingPreference(BaseModel):
    enabled: bool


def get_tracker_or_503():
    tracker = getattr(app.state, "tracker", None)
    if tracker is None:
        raise HTTPException(status_code=503, detail="Collector is starting.")
    return tracker


@app.get("/live/recording")
def get_live_recording():
    tracker = get_tracker_or_503()
    return {"enabled": tracker.recording_enabled}


@app.put("/live/recording")
def set_live_recording(preference: RecordingPreference):
    tracker = get_tracker_or_503()
    return {"enabled": tracker.set_recording_enabled(preference.enabled)}


@app.websocket("/ws/live")
async def live_telemetry(websocket: WebSocket):
    """Stream fresh latest-only GT7 frames, capped at 25 updates per second."""
    await websocket.accept()
    hub: LiveTelemetryHub = websocket.app.state.live_hub
    hub.connect()
    sequence = 0
    last_frame_sent = 0.0
    last_status_sent = 0.0
    current_status = ""
    stale_after_seconds = 1.5
    sent_track_session: int | None = None

    async def send_status(status: str, message: str, *, force: bool = False):
        nonlocal current_status, last_status_sent
        now = time.monotonic()
        if force or status != current_status or now - last_status_sent >= 2:
            await websocket.send_json(
                {"type": "status", "status": status, "message": message}
            )
            current_status = status
            last_status_sent = now

    try:
        await send_status(
            "waiting", "Waiting for GT7 telemetry from the collector.", force=True
        )
        # A reconnect gets the server-held map immediately.
        initial = hub.snapshot(include_track=True)
        if initial is not None:
            sequence, frame = initial
            if max(0.0, time.time() - frame.captured_at) <= stale_after_seconds:
                await websocket.send_json(
                    {
                        "type": "frame",
                        "status": "live",
                        "age_ms": max(0, round((time.time() - frame.captured_at) * 1000)),
                        "frame": frame.model_dump(mode="json"),
                    }
                )
                current_status = "live"
                last_frame_sent = time.monotonic()
                if frame.track_ready and frame.track_trace:
                    sent_track_session = frame.session_id
        while True:
            update = await asyncio.to_thread(hub.wait_for_update, sequence, 0.5)
            snapshot = update or hub.snapshot()
            if snapshot is None:
                await send_status(
                    "waiting", "Waiting for GT7 telemetry from the collector."
                )
                continue

            latest_sequence, frame = snapshot
            age = max(0.0, time.time() - frame.captured_at)
            if age > stale_after_seconds:
                sequence = latest_sequence
                await send_status(
                    "stale",
                    "GT7 telemetry signal is stale. Check the game and collector.",
                )
                continue

            if update is None or latest_sequence <= sequence:
                continue

            wait = 0.04 - (time.monotonic() - last_frame_sent)
            if wait > 0:
                await asyncio.sleep(wait)
                latest = hub.snapshot()
                if latest is not None:
                    latest_sequence, frame = latest

            # Latest-only coalescing can discard the packet carrying the completed
            # outline. Recover it once per connection/session, including when it
            # was replaced during the throttle sleep. Completed geometry is fixed
            # for the session; subsequent hot frames keep their small payloads.
            if frame.track_ready and frame.session_id != sent_track_session:
                complete = hub.snapshot(include_track=True)
                if complete is not None:
                    latest_sequence, frame = complete

            sequence = latest_sequence
            age_ms = max(0, round((time.time() - frame.captured_at) * 1000))
            await websocket.send_json(
                {
                    "type": "frame",
                    "status": "live",
                    "age_ms": age_ms,
                    "frame": frame.model_dump(mode="json"),
                }
            )
            current_status = "live"
            last_frame_sent = time.monotonic()
            if not frame.track_ready:
                sent_track_session = None
            elif frame.track_trace:
                sent_track_session = frame.session_id
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.disconnect()


@app.get("/tracks")
def get_tracks_list(db: Session = Depends(get_db), q: str = Query()):
    query = select(Track).order_by(asc(Track.name))
    if q:
        query = query.where(col(Track.name).contains(q))

    res = db.execute(query).scalars().all()
    return res


@app.get("/cars")
def get_cars_list(db: Session = Depends(get_db)):
    query = select(Car).order_by(asc(Car.id))
    res = db.execute(query).scalars().all()
    return res


@app.get("/cars/{car_id}")
def get_car_detail(car_id: str, db: Session = Depends(get_db)):
    query = select(Car).where(Car.id == car_id)
    res = db.execute(query).scalar_one_or_none()
    return res


@app.get("/sessions")
def get_sessions_list(db: Session = Depends(get_db)):
    query = select(Race).order_by(desc(Race.end_ts))
    res = db.execute(query).scalars().all()
    return res


@app.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    session = db.get(Race, session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' was not found."
        )

    lap_count = len(
        db.execute(select(Lap).where(Lap.race_id == session_id)).scalars().all()
    )
    return {
        "session": session,
        "lap_count": lap_count,
        "car": db.get(Car, session.car_id),
        "track": db.get(Track, session.track_id)
        if session.track_id is not None
        else None,
    }


@app.get("/sessions/{session_id}/laps")
def get_session_laps_list(session_id: str, db: Session = Depends(get_db)):
    session = db.get(Race, session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' was not found."
        )

    query = select(Lap).where(Lap.race_id == session_id).order_by(asc(Lap.number))
    res = db.execute(query).scalars().all()
    return res


def get_lap_or_404(session_id: str, lap_number: int, db: Session) -> Lap:
    lap = db.execute(
        select(Lap).where(Lap.race_id == session_id, Lap.number == lap_number)
    ).scalar_one_or_none()
    if lap is None:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} was not found in session '{session_id}'.",
        )
    return lap


def read_lap_csv_or_404(session_id: str, lap_number: int) -> pd.DataFrame:
    path_to_dump = DATA_DIR / session_id / f"lap_{lap_number}.csv"
    if not path_to_dump.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Telemetry CSV for lap {lap_number} is not available in session '{session_id}'.",
        )
    try:
        return pd.read_csv(path_to_dump)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read telemetry CSV for lap {lap_number}: {error}",
        ) from error


@app.get("/sessions/{session_id}/compare")
def get_lap_comparison(
    session_id: str,
    lap_a: int = Query(alias="lapA"),
    lap_b: int = Query(alias="lapB"),
    db: Session = Depends(get_db),
):
    if db.get(Race, session_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' was not found."
        )

    selected_a = get_lap_or_404(session_id, lap_a, db)
    selected_b = get_lap_or_404(session_id, lap_b, db)
    try:
        comparison = compare_laps(
            read_lap_csv_or_404(session_id, lap_a),
            selected_a.time,
            read_lap_csv_or_404(session_id, lap_b),
            selected_b.time,
        )
    except ComparisonError as error:
        return {
            "available": False,
            "warning": str(error),
            "lap_a_time_ms": selected_a.time,
            "lap_b_time_ms": selected_b.time,
        }

    return {
        "available": True,
        "warning": None,
        "lap_a_time_ms": selected_a.time,
        "lap_b_time_ms": selected_b.time,
        **comparison,
    }


@app.get("/sessions/{session_id}/laps/{lap_number}")
def get_lap_telemetry(session_id: str, lap_number: int, db: Session = Depends(get_db)):
    session = db.get(Race, session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' was not found."
        )

    get_lap_or_404(session_id, lap_number, db)
    data = read_lap_csv_or_404(session_id, lap_number).to_dict("records")

    return data


@app.get("/layouts")
def get_track_layouts_list():
    layouts = []
    for left_border in PROJECT_ROOT.joinpath("track_layouts").rglob("left.csv"):
        layout_dir = left_border.parent
        if "source" in layout_dir.parts or not (layout_dir / "right.csv").is_file():
            continue
        layouts.append(
            layout_dir.relative_to(PROJECT_ROOT / "track_layouts").as_posix()
        )
    return sorted(layouts)


@app.get("/layouts/{track_name:path}")
def get_track_layout(track_name: str):
    layouts_root = (PROJECT_ROOT / "track_layouts").resolve()
    path_to_dump = (layouts_root / track_name).resolve()
    if (
        not path_to_dump.is_relative_to(layouts_root)
        or not (path_to_dump / "left.csv").is_file()
        or not (path_to_dump / "right.csv").is_file()
    ):
        raise HTTPException(
            status_code=404, detail=f"Track layout '{track_name}' was not found."
        )

    data = [
        pd.read_csv(path_to_dump / f"{border}.csv").to_dict("records")
        for border in ["left", "right"]
    ]

    return data

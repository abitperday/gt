"""Run the GT7 collector and FastAPI live hub in one process."""

import os
import threading

import uvicorn

from src.receivers.gt7 import GT7Receiver
from src.services.tracker import Tracker
from src.storage import Storage
from web import app


def main():
    host = os.getenv("GT7_API_HOST", "0.0.0.0")
    api_port = int(os.getenv("GT7_API_PORT", "8000"))
    playstation_ip = os.getenv("GT7_PS_IP", "192.168.100.12")
    playstation_port = int(os.getenv("GT7_PS_PORT", "33740"))

    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=api_port, log_level="info")
    )
    api_thread = threading.Thread(target=server.run, name="gt7-api", daemon=True)
    api_thread.start()

    tracker = Tracker(db=Storage(verbose=True), live_hub=app.state.live_hub)
    receiver = GT7Receiver(playstation_ip, playstation_port)
    try:
        for event in receiver.stream_events():
            tracker.process_event(event)
    finally:
        server.should_exit = True
        api_thread.join(timeout=5)


if __name__ == "__main__":
    main()

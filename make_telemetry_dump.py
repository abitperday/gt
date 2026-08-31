from src.receivers.gt7 import GT7Receiver
from src.schema.telemetry import TelemetryStat

from src.services.tracker import Tracker
from src.storage import Storage

PS_IP = '192.168.1.27'
PS_PORT = 33740

tracker = Tracker(
    db=Storage(verbose=True),
)

receiver = GT7Receiver(PS_IP, PS_PORT)
prev_event = None
for event in receiver.stream_events():
    stat: TelemetryStat = TelemetryStat.from_bytes(event, prev_event)
    print(stat.model_dump_json())
    prev_event = stat
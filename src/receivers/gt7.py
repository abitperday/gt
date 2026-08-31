import socket
from typing import Iterator, Optional

from Crypto.Cipher import Salsa20

from src.receivers.base import BaseReceiver


class GT7Receiver(BaseReceiver):
    _heartbeat_port: int
    _socket: socket.socket

    def __init__(self, ip: str, port: int):
        super().__init__(ip, port)

        self._heartbeat_port = 33739

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(("0.0.0.0", self._port))
        self._socket.settimeout(2)
        print("CONNECTED")

    def decode_msg(self, data: bytes) -> Optional[bytes]:
        KEY = b"Simulator Interface Packet GT7 ver 0.0"
        # Seed IV is always located here
        oiv = data[0x40:0x44]
        iv1 = int.from_bytes(oiv, byteorder="little")
        # Notice DEADBEAF, not DEADBEEF
        iv2 = iv1 ^ 0xDEADBEAF
        IV = bytearray()
        IV.extend(iv2.to_bytes(4, "little"))
        IV.extend(iv1.to_bytes(4, "little"))
        cipher = Salsa20.new(KEY[0:32], bytes(IV))
        ddata = cipher.decrypt(data)
        magic = int.from_bytes(ddata[0:4], byteorder="little")
        if magic != 0x47375330:
            return None

        return ddata

    def stream_events(self) -> Iterator[bytes]:
        def send_heartbeat():
            send_data = "A"
            self._socket.sendto(
                send_data.encode("utf-8"), (self._ip, self._heartbeat_port)
            )

        pkgcnt = 0
        while True:
            try:
                data, _ = self._socket.recvfrom(4096)
                pkgcnt += 1
                rec = self.decode_msg(data)

                if not rec:
                    continue

                yield rec

                if pkgcnt > 100:
                    send_heartbeat()
                    pkgcnt = 0
            except Exception:
                send_heartbeat()
                pkgcnt = 0

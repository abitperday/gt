import abc


class BaseReceiver(abc.ABC):
    _ip: str
    _port: int

    def __init__(self, ip: str, port: int):
        self._ip = ip
        self._port = port

    def decode_msg(self, data: bytes):
        raise NotImplementedError()

    def stream_events(self):
        raise NotImplementedError

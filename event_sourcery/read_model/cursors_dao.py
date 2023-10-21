import abc

from event_sourcery.event_store import StreamId


class CursorsDao(abc.ABC):
    class StreamNotTracked(Exception):
        pass

    class BehindStream(Exception):
        def __init__(self, current_version: int) -> None:
            self.current_version = current_version
            super().__init__()

    class AheadOfStream(Exception):
        def __init__(self, current_version: int) -> None:
            self.current_version = current_version
            super().__init__()

    @abc.abstractmethod
    def increment(self, name: str, stream_id: StreamId, version: int) -> None:
        pass

    @abc.abstractmethod
    def put_at(self, name: str, stream_id: StreamId, version: int) -> None:
        pass

    @abc.abstractmethod
    def move_to(self, name: str, stream_id: StreamId, version: int) -> None:
        pass

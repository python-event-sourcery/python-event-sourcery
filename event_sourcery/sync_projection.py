import abc

from event_sourcery.event import Event


class SyncProjection(abc.ABC):
    @abc.abstractmethod
    def handle(self, event: Event) -> None:
        pass

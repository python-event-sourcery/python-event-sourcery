from contextlib import contextmanager
from typing import Iterator

from event_sourcery.interfaces.event import Event


class Aggregate:
    def __init__(self) -> None:
        self.__changes: list[Event] = []

    @contextmanager
    def __persisting_changes__(self) -> Iterator[Iterator[Event]]:
        yield iter(self.__changes)
        self.__changes = []

    def __apply__(self, event: Event) -> None:
        raise NotImplementedError

    def _emit(self, event: Event) -> None:
        self.__apply__(event)
        self.__changes.append(event)

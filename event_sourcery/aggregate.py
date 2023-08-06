from contextlib import contextmanager
from typing import ClassVar, Iterator

from event_sourcery.interfaces.base_event import Event


class Aggregate:
    category: ClassVar[str]

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

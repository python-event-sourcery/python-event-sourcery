from typing import ClassVar, Protocol, Type

from event_sourcery.interfaces.event import TEvent


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type[TEvent], str] = {}
        self._names_to_types: dict[str, Type[TEvent]] = {}

    def add(self, event: Type[TEvent]) -> Type[TEvent]:
        if event.name in self._types_to_names.values():
            raise Exception(f"Duplicated Event name detected! {event.name}")

        self._types_to_names[event] = event.name
        self._names_to_types[event.name] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> Type[TEvent]:
        return self._names_to_types[name]

    def name_for_type(self, event: Type[TEvent]) -> str:
        return self._types_to_names[event]


class BaseEventCls(Protocol):
    __registry__: ClassVar[EventRegistry]

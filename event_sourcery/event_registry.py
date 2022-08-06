from typing import ClassVar, Protocol, Type

from event_sourcery.interfaces.event import Event


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type[Event], str] = {}
        self._names_to_types: dict[str, Type[Event]] = {}

    def add(self, event: Type[Event]) -> Type[Event]:
        if event.__name__ in self._types_to_names.values():
            raise Exception(f"Duplicated Event name detected! {event.__name__}")

        self._types_to_names[event] = event.__name__
        self._names_to_types[event.__name__] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> Type[Event]:
        return self._names_to_types[name]

    def name_for_type(self, event: Type[Event]) -> str:
        return self._types_to_names[event]


class BaseEventCls(Protocol):
    __registry__: ClassVar[EventRegistry]

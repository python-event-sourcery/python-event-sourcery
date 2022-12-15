import inspect
from typing import ClassVar, Protocol, Type

from event_sourcery.interfaces.event import TEvent


def event_name(cls: Type) -> str:
    event_module = inspect.getmodule(cls)
    return f'{event_module.__name__}.{cls.__qualname__}'


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type[TEvent], str] = {}
        self._names_to_types: dict[str, Type[TEvent]] = {}

    def add(self, event: Type[TEvent]) -> Type[TEvent]:
        if event in self._types_to_names:
            raise Exception(f"Duplicated Event name detected! {event.name}")

        name = event_name(event)
        self._types_to_names[event] = name
        self._names_to_types[name] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> Type[TEvent]:
        return self._names_to_types[name]

    def name_for_type(self, event: Type[TEvent]) -> str:
        return self._types_to_names[event]


class BaseEventCls(Protocol):
    __registry__: ClassVar[EventRegistry]

import inspect
from typing import TypeAlias

from pydantic import BaseModel

from event_sourcery.event_store.event.dto import Event
from event_sourcery.event_store.exceptions import (
    ClassModuleUnavailable,
    DuplicatedEvent,
)

TEvent: TypeAlias = BaseModel


def event_name(cls: type) -> str:
    if name := getattr(cls, "__event_name__", ""):
        return name

    event_module = inspect.getmodule(cls)
    if event_module is None:  # pragma: no cover
        raise ClassModuleUnavailable
    return f"{event_module.__name__}.{cls.__qualname__}"


class EventRegistry:
    """Keeps mappings between event types and their names.

    Normally, there is no need to use it directly. If one needs to have multiple
    registries or wants more granular control, they can pass an instance
    of EventRegistry to BackendFactory."""

    def __init__(self) -> None:
        self._types_to_names: dict[type[TEvent], str] = {}
        self._names_to_types: dict[str, type[TEvent]] = {}
        self._register_defined_events()

    def _register_defined_events(self) -> None:
        for event_type in Event.__subclasses__():
            event_type not in self._types_to_names and self.add(event_type)

    def add(self, event: type[TEvent]) -> type[TEvent]:
        """Add event subclass to the registry."""
        if event in self._types_to_names:
            raise DuplicatedEvent(f"Duplicated Event detected! {event}")

        name = event_name(event)
        if name in self._names_to_types:
            raise DuplicatedEvent(f"Duplicated Event name detected! {name}")

        self._types_to_names[event] = name
        self._names_to_types[name] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> type[TEvent]:
        if name not in self._names_to_types:
            self._register_defined_events()
        return self._names_to_types[name]

    def name_for_type(self, event: type[TEvent]) -> str:
        if event not in self._types_to_names:
            self._register_defined_events()
        return self._types_to_names[event]

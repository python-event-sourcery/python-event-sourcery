import inspect
from typing import TYPE_CHECKING

from event_sourcery.event_store.exceptions import (
    ClassModuleUnavailable,
    DuplicatedEvent,
)

if TYPE_CHECKING:
    from event_sourcery.event_store.event.dto import Event


def event_name(cls: type) -> str:
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
        self._types_to_names: dict[type[Event], str] = {}
        self._names_to_types: dict[str, type[Event]] = {}

    def add(self, event: type["Event"]) -> type["Event"]:
        """Add event subclass to the registry."""
        if event in self._types_to_names:
            raise DuplicatedEvent(f"Duplicated Event detected! {event}")

        name = event_name(event)
        if name in self._names_to_types:
            raise DuplicatedEvent(f"Duplicated Event name detected! {name}")

        self._types_to_names[event] = name
        self._names_to_types[name] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> type["Event"]:
        return self._names_to_types[name]

    def name_for_type(self, event: type["Event"]) -> str:
        return self._types_to_names[event]

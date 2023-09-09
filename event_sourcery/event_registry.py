import inspect
from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from event_sourcery.interfaces.base_event import Event


class ClassModuleUnavailable(Exception):
    pass


class DuplicatedEvent(Exception):
    pass


def event_name(cls: Type) -> str:
    event_module = inspect.getmodule(cls)
    if event_module is None:  # pragma: no cover
        raise ClassModuleUnavailable
    return f"{event_module.__name__}.{cls.__qualname__}"


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type["Event"], str] = {}
        self._names_to_types: dict[str, Type["Event"]] = {}

    def add(self, event: Type["Event"]) -> Type["Event"]:
        if event in self._types_to_names:
            raise DuplicatedEvent(f"Duplicated Event detected! {event}")

        name = event_name(event)
        if name in self._names_to_types:
            raise DuplicatedEvent(f"Duplicated Event name detected! {name}")

        self._types_to_names[event] = name
        self._names_to_types[name] = event
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> Type["Event"]:
        return self._names_to_types[name]

    def name_for_type(self, event: Type["Event"]) -> str:
        return self._types_to_names[event]

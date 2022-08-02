from collections import Counter
from typing import ClassVar, Protocol, Type

from event_sourcery.interfaces.event import Event


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type[Event], str] = {}
        self._names_to_types: dict[str, Type[Event]] = {}

    def add(self, event: Type[Event]) -> None:
        self._types_to_names[event] = event.__name__
        counted_names = Counter(self._types_to_names.values())
        duplicated_names = {key for key, value in counted_names.items() if value > 1}
        if duplicated_names:
            raise Exception(f"Duplicated Event name detected! {duplicated_names}")

        self._names_to_types[event.__name__] = event

    def type_for_name(self, name: str) -> Type[Event]:
        return self._names_to_types[name]

    def name_for_type(self, event: Type[Event]) -> str:
        return self._types_to_names[event]


class BaseEventCls(Protocol):
    __registry__: ClassVar[EventRegistry]

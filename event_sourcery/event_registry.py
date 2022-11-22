from typing import ClassVar, Protocol, Type, Optional

from event_sourcery.interfaces.event import Event


class EventRegistry:
    def __init__(self) -> None:
        self._types_to_names: dict[Type[Event], str] = {}
        self._names_to_types: dict[str, Type[Event]] = {}

    def add(self, event: Type[Event]) -> Type[Event]:
        if event.name in self._types_to_names.values():
            raise Exception(f"Duplicated Event name detected! {event.name}")

        self._types_to_names[event] = event.name
        self._names_to_types[event.name] = event
        print(self._types_to_names)
        print(self._names_to_types)
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> Type[Event]:
        # print("Type for name", name, self._names_to_types[name])
        return self._names_to_types[name]

    def name_for_type(self, event: Type[Event]) -> str:
        # print("Name for type", type, self._types_to_names[event])
        return self._types_to_names[event]


class BaseEventCls(Protocol):
    __registry__: ClassVar[EventRegistry]

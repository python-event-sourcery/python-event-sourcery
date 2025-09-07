import inspect
from typing import Annotated, TypeAlias, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from event_sourcery.event_store.event._dto import DataSubject, Encrypted, Event
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


def get_encrypted_fields(of: type) -> dict[str, Encrypted]:
    fields = {}
    for field, hint in get_type_hints(of, include_extras=True).items():
        if isinstance(hint, type):
            fields.update(
                {
                    f"{field}.{nested}": encrypted
                    for nested, encrypted in get_encrypted_fields(hint).items()
                }
            )
        elif get_origin(hint) is Annotated:
            _, *metadata = get_args(hint)
            encrypted = next((m for m in metadata if isinstance(m, Encrypted)), None)
            if encrypted:
                fields[field] = encrypted
    return fields


def get_data_subject_filed(of: type[BaseModel]) -> str | None:
    return next(
        (
            field_name
            for field_name, field_info in of.model_fields.items()
            if DataSubject in field_info.metadata
        ),
        None,
    )


class EventRegistry:
    """Keeps mappings between event types and their names.

    Normally, there is no need to use it directly. If one needs to have multiple
    registries or wants more granular control, they can pass an instance
    of EventRegistry to BackendFactory."""

    def __init__(self) -> None:
        self._types_to_names: dict[type[TEvent], str] = {}
        self._names_to_types: dict[str, type[TEvent]] = {}
        self._encrypted_fields: dict[type[TEvent], dict[str, Encrypted]] = {}
        self._subject_fields: dict[type[TEvent], str] = {}
        self._register_defined_events()

    def _register_defined_events(self) -> None:
        for event_type in Event.__subclasses__():
            not_registered_type = event_type not in self._types_to_names
            not_registered_name = event_name(event_type) not in self._names_to_types
            not_registered_type and not_registered_name and self.add(event_type)

    def add(self, event: type[TEvent]) -> type[TEvent]:
        """Add event subclass to the registry."""
        if event in self._types_to_names:
            raise DuplicatedEvent(f"Duplicated Event detected! {event}")

        name = event_name(event)
        if name in self._names_to_types:
            raise DuplicatedEvent(f"Duplicated Event name detected! {name}")

        self._types_to_names[event] = name
        self._names_to_types[name] = event
        self._encrypted_fields[event] = get_encrypted_fields(of=event)
        subject_field = get_data_subject_filed(of=event)
        if subject_field is not None:
            self._subject_fields[event] = subject_field
        return event  # for use as a decorator

    def type_for_name(self, name: str) -> type[TEvent]:
        if name not in self._names_to_types:
            self._register_defined_events()
        return self._names_to_types[name]

    def name_for_type(self, event: type[TEvent]) -> str:
        if event not in self._types_to_names:
            self._register_defined_events()
        return self._types_to_names[event]

    def encrypted_fields(self, of: type[TEvent]) -> dict[str, Encrypted]:
        return self._encrypted_fields[of]

    def subject_filed(self, for_field: str, of: type[TEvent]) -> str | None:
        metadata = self._encrypted_fields[of].get(for_field)
        return (metadata and metadata.subject_field) or self._subject_fields.get(of)

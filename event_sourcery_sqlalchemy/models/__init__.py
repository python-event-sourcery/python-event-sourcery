from typing import Protocol

from sqlalchemy import MetaData
from sqlalchemy.orm import registry
from sqlalchemy.orm.clsregistry import ClsRegistryToken

from event_sourcery_sqlalchemy.models.base import (
    BaseEvent,
    BaseOutboxEntry,
    BaseProjectorCursor,
    BaseSnapshot,
    BaseStream,
)
from event_sourcery_sqlalchemy.models.default import (
    DefaultEvent,
    DefaultOutboxEntry,
    DefaultProjectorCursor,
    DefaultSnapshot,
    DefaultStream,
)


class BaseProto(Protocol):
    metadata: MetaData


_class_registry: dict[str, type | ClsRegistryToken] = {}


def configure_models(
    base: type[BaseProto],
    event_model: type[BaseEvent] = DefaultEvent,
    stream_model: type[BaseStream] = DefaultStream,
    snapshot_model: type[BaseSnapshot] = DefaultSnapshot,
    outbox_entry_model: type[BaseOutboxEntry] = DefaultOutboxEntry,
    projector_cursor_model: type[BaseProjectorCursor] = DefaultProjectorCursor,
) -> None:
    """
    Configures SQLAlchemy ORM models for Event Sourcery backend.

    Sets up mapping information and registers the provided (or default) models with
    SQLAlchemy's registry.
    This function allows customization of event, stream, snapshot, outbox entry, and
    projector cursor models for advanced scenarios, or uses the default models for
    standard usage.
    Ensures all models are mapped declaratively and share the same metadata and class
    registry, enabling flexible schema management and migrations.

    Args:
        base (type[BaseProto]):
            Base class providing SQLAlchemy MetaData for model registration.
        event_model (type[BaseEvent], optional):
            Event model class to use. Defaults to DefaultEvent.
        stream_model (type[BaseStream], optional):
            Stream model class to use. Defaults to DefaultStream.
        snapshot_model (type[BaseSnapshot], optional):
            Snapshot model class to use. Defaults to DefaultSnapshot.
        outbox_entry_model (type[BaseOutboxEntry], optional):
            Outbox entry model class to use. Defaults to DefaultOutboxEntry.
        projector_cursor_model (type[BaseProjectorCursor], optional):
            Projector cursor model class to use. Defaults to DefaultProjectorCursor.
    """
    event_model.__set_mapping_information__(stream_model)
    snapshot_model.__set_mapping_information__(stream_model)
    stream_model.__set_mapping_information__(event_model, snapshot_model)

    mapping_registry = registry(metadata=base.metadata, class_registry=_class_registry)
    for model_cls in (
        stream_model,
        event_model,
        snapshot_model,
        outbox_entry_model,
        projector_cursor_model,
    ):
        if model_cls in _class_registry.values():
            continue

        mapping_registry.map_declaratively(model_cls)

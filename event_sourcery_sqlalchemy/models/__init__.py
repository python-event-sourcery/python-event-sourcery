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

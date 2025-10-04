from typing import Any

from sqlalchemy.orm import registry

from event_sourcery_sqlalchemy.models.default import (
    DefaultEvent,
    DefaultOutboxEntry,
    DefaultProjectorCursor,
    DefaultSnapshot,
    DefaultStream,
)


def configure_models(base: type[Any]) -> None:
    DefaultEvent.__set_mapping_information__(DefaultStream)
    DefaultSnapshot.__set_mapping_information__(DefaultStream)
    DefaultStream.__set_mapping_information__(DefaultEvent, DefaultSnapshot)

    for model_cls in (
        DefaultStream,
        DefaultEvent,
        DefaultSnapshot,
        DefaultOutboxEntry,
        DefaultProjectorCursor,
    ):
        registry(metadata=base.metadata, class_registry={}).map_declaratively(model_cls)

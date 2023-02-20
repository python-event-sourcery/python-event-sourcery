from dataclasses import dataclass, field
from typing import Type

from event_sourcery.interfaces.base_event import Event


class InvalidSubscription(Exception):
    pass


@dataclass(frozen=True)
class Subscription:
    event_types: list[Type[Event]] = field(default_factory=list)
    stream_categories: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.event_types) == 0 and len(self.stream_categories) == 0:
            raise InvalidSubscription(
                "At least one event type or stream category needs to be specified"
            )

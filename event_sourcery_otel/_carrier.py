from typing import ClassVar

from event_sourcery.event import ContextComponent


class OpenTelemetryCarrier(ContextComponent):
    __context_name__: ClassVar[str] = "opentelemetry"

    values: dict[str, str]

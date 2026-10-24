import pytest

from event_sourcery.backend import InMemoryBackend
from event_sourcery_otel import OpenTelemetryContextEnricher
from tests.otel.bdd import Otel


@pytest.fixture
def otel() -> Otel:
    return Otel()


@pytest.fixture
def backend() -> InMemoryBackend:
    return InMemoryBackend().with_context_enrichers(OpenTelemetryContextEnricher())

from unittest.mock import call

import pytest

from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.stream import StreamId
from tests.bdd import Given
from tests.event_store.outbox.conftest import PublisherMock
from tests.factories import an_event
from tests.matchers import any_record


def test_receives_events_from_all_tenants(
    publisher: PublisherMock,
    backend: Backend,
    given: Given,
) -> None:
    given.in_tenant_mode("first").event(first := an_event(), on=StreamId())
    given.in_tenant_mode("second").event(second := an_event(), on=StreamId())
    given.in_tenant_mode("third").event(third := an_event(version=1), on=StreamId())

    backend.outbox.run(publisher)

    assert publisher.call_args_list == [
        call(any_record(first, for_tenant="first")),
        call(any_record(second, for_tenant="second")),
        call(any_record(third, for_tenant="third")),
    ]


@pytest.fixture()
def backend(backend: Backend) -> Backend:
    return backend.with_outbox()

import pytest

from event_sourcery.event_store import StreamId
from event_sourcery.event_store.context import event_sourcery_context
from tests.bdd import Given, Then
from tests.factories import an_event

pytestmark = pytest.mark.skip_backend(
    backend=["esdb", "in_memory", "sqlalchemy_sqlite", "sqlalchemy_postgres"],
    reason="Skipped for now, for the sake of PoC.",
)


def test_one_tenant_doesnt_see_streams_of_other_tenants(
    given: Given,
    then: Then,
) -> None:
    with event_sourcery_context(tenant_id=1):
        events = [an_event() for _ in range(3)]
        stream_1 = given.stream().with_events(*events)
    with event_sourcery_context(tenant_id=2):
        stream_2 = given.stream().with_events(*[an_event() for _ in range(3)])

    with event_sourcery_context(tenant_id=1):
        then.stream(stream_1.id).loads_only(events)
        then.stream(stream_2.id).is_empty()


def test_context_is_reentrant(
    given: Given,
    then: Then,
) -> None:
    with event_sourcery_context(tenant_id=1):
        events = [an_event(), an_event()]
        stream = given.stream().with_events(*events)

    with event_sourcery_context(tenant_id=2):
        then.stream(stream.id).is_empty()

        with event_sourcery_context(tenant_id=1):
            then.stream(stream.id).loads_only(events)

            with event_sourcery_context(tenant_id=2):
                then.stream(stream.id).is_empty()


@pytest.mark.xfail(reason="Not implemented")
def test_streams_with_same_id_under_different_tenants_are_allowed(
    given: Given,
    then: Then,
) -> None:
    stream_id = StreamId()
    with event_sourcery_context(tenant_id=1):
        event_of_first_tenant = an_event()
        given.stream(stream_id).with_events(event_of_first_tenant)

    with event_sourcery_context(tenant_id=2):
        event_of_second_tenant = an_event()
        # TODO: should this raise an exception? Should this pass?
        given.stream(stream_id).with_events(event_of_second_tenant)

    with event_sourcery_context(tenant_id=1):
        then.stream(stream_id).loads_only([event_of_first_tenant])

    with event_sourcery_context(tenant_id=2):
        then.stream(stream_id).loads_only([event_of_second_tenant])


@pytest.mark.xfail(reason="Not implemented")
def test_streams_created_in_tenant_aware_context_are_not_available_outside(
    given: Given,
    then: Then,
) -> None:
    stream_id = StreamId()
    with event_sourcery_context(tenant_id=1):
        given.stream(stream_id).with_events(an_event())

    then.stream(stream_id).is_empty()


@pytest.mark.xfail(reason="Not implemented")
def test_streams_created_outside_tenant_context_are_not_available_inside_it(
    given: Given,
    then: Then,
) -> None:
    stream_id = StreamId()
    given.stream(stream_id).with_events(an_event())

    with event_sourcery_context(tenant_id=1):
        then.stream(stream_id).is_empty()

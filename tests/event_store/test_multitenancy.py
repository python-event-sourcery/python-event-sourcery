import pytest

from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.exceptions import IllegalTenantId
from event_sourcery.event_store.stream import StreamId
from tests.bdd import Given, Then
from tests.factories import AnEvent, an_event


def test_stream_created_in_default_context_cannot_be_accessed_from_tenant_context(
    given: Given,
    then: Then,
) -> None:
    given.event(an_event(), on=(stream_id := StreamId()))
    then.in_tenant_mode("tenant").stream(with_id=stream_id).is_empty()


def test_stream_created_in_tenant_context_cannot_be_accessed_in_default_context(
    given: Given,
    then: Then,
) -> None:
    given.in_tenant_mode("tenant").event(an_event(), on=(stream_id := StreamId()))
    then.without_tenant().stream(with_id=stream_id).is_empty()


def test_streams_with_same_id_or_name_can_coexist(
    given: Given,
    then: Then,
) -> None:
    stream_id = StreamId()
    given.without_tenant().event(without_tenant_event := an_event(), on=stream_id)
    given.in_tenant_mode("first").event(tenant_1_event := an_event(), on=stream_id)
    given.in_tenant_mode("second").event(tenant_2_event := an_event(), on=stream_id)

    then.without_tenant().stream(with_id=stream_id).loads_only([without_tenant_event])
    then.in_tenant_mode("first").stream(with_id=stream_id).loads_only([tenant_1_event])
    then.in_tenant_mode("second").stream(with_id=stream_id).loads_only([tenant_2_event])


def test_kurrentdb_cant_use_tenant_id_with_dash(kurrentdb_backend: Backend) -> None:
    illegal_tenant = kurrentdb_backend.in_tenant_mode("illegal-tenant-id")
    illegal_tenant_event_store = illegal_tenant.event_store

    with pytest.raises(IllegalTenantId):
        illegal_tenant_event_store.append(AnEvent(), stream_id=StreamId())

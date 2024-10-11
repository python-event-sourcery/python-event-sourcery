import pytest

from event_sourcery.event_store import Event, EventStore, StreamId

pytestmark = pytest.mark.skip_backend(
    backend=["esdb", "django"],
    reason="Skipped for now, for the sake of PoC.",
)


class TenantCreated(Event):
    message: str


@pytest.mark.parametrize("stream_id", [StreamId(), StreamId(name="stream1")])
def test_stream_created_in_default_context_cannot_be_accessed_from_tenant_context(
    event_store: EventStore, stream_id: StreamId
) -> None:
    event_store.append(TenantCreated(message="Hello"), stream_id=stream_id)

    tenant1_event_store = event_store.scoped_for_tenant("tenant1")
    events = tenant1_event_store.load_stream(stream_id)

    assert len(events) == 0


@pytest.mark.parametrize("stream_id", [StreamId(), StreamId(name="stream1")])
def test_stream_created_in_tenant_context_cannot_be_accessed_in_default_context(
    event_store: EventStore, stream_id: StreamId
) -> None:
    tenant_1 = event_store.scoped_for_tenant("tenant1")
    tenant_1.append(TenantCreated(message="Hello 1!"), stream_id=stream_id)

    default_tenant = event_store
    events = default_tenant.load_stream(stream_id)

    assert len(events) == 0


@pytest.mark.parametrize("stream_id", [StreamId(), StreamId(name="stream1")])
def test_streams_with_same_id_or_name_can_coexist(
    event_store: EventStore, stream_id: StreamId
) -> None:
    default_tenant = event_store
    tenant_1 = event_store.scoped_for_tenant("tenant1")
    tenant_2 = event_store.scoped_for_tenant("tenant")

    default_tenant.append(
        tenantless_event := TenantCreated(message="Hello anon!"), stream_id=stream_id
    )
    tenant_1.append(
        tenant_1_event := TenantCreated(message="Hello 1!"), stream_id=stream_id
    )
    tenant_2.append(
        tenant_2_event := TenantCreated(message="Hello 2!"), stream_id=stream_id
    )

    default_tenant_stream = default_tenant.load_stream(stream_id)
    assert len(default_tenant_stream) == 1
    assert default_tenant_stream[0].event == tenantless_event
    tenant_1_stream = tenant_1.load_stream(stream_id)
    assert len(tenant_1_stream) == 1
    assert tenant_1_stream[0].event == tenant_1_event
    tenant_2_stream = tenant_2.load_stream(stream_id)
    assert len(tenant_2_stream) == 1
    assert tenant_2_stream[0].event == tenant_2_event

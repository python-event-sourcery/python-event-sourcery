from uuid import uuid4

from event_sourcery import StreamId, StreamUUID
from event_sourcery._event_store.event.dto import Context
from event_sourcery.event_sourcing import Repository

from .light_switch import LightSwitch


def test_wrapped_aggregate_provides_access_to_aggregate(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()
        assert wrapped.aggregate.shines is True


def test_wrapped_aggregate_is_new_when_no_prior_events(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.is_new is True


def test_wrapped_aggregate_is_not_new_after_reload(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.is_new is False


def test_wrapped_aggregate_is_new_even_after_emitting_events(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()
        assert wrapped.is_new is True


def test_wrapped_aggregate_version_starts_at_zero_for_new(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.version == 0


def test_wrapped_aggregate_version_reflects_stored_events(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.version == 1


def test_wrapped_aggregate_version_includes_pending_changes(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.version == 0
        wrapped.aggregate.turn_on()
        assert wrapped.version == 1
        wrapped.aggregate.turn_off()
        assert wrapped.version == 2


def test_wrapped_aggregate_version_combines_stored_and_pending(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.version == 1
        wrapped.aggregate.turn_off()
        assert wrapped.version == 2


def test_wrapped_aggregate_exposes_stream_id(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.stream_id == StreamId(uuid, category=LightSwitch.category)


def test_wrapped_aggregate_timestamps_are_none_for_new(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.created_at is None
        assert wrapped.updated_at is None


def test_wrapped_aggregate_timestamps_after_events_persisted(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.created_at is not None
        assert wrapped.updated_at is not None
        assert wrapped.created_at == wrapped.updated_at


def test_wrapped_aggregate_updated_at_differs_from_created_at_with_multiple_events(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()
        wrapped.aggregate.turn_off()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.created_at is not None
        assert wrapped.updated_at is not None
        assert wrapped.created_at <= wrapped.updated_at


def test_wrapped_aggregate_exposes_context(
    repo: Repository[LightSwitch],
) -> None:
    class RequestContext(Context):
        user_id: str

    uuid = StreamUUID(uuid4())
    ctx = RequestContext(user_id="user-123")
    with repo.aggregate(uuid, LightSwitch(), context=ctx) as wrapped:
        assert wrapped.context == ctx
        assert wrapped.get_context(RequestContext).user_id == "user-123"


def test_wrapped_aggregate_context_is_default_when_not_provided(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        assert wrapped.context == Context()

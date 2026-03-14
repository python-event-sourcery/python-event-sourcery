from uuid import uuid4

import pytest

from event_sourcery import EventStore, StreamId, StreamUUID
from event_sourcery.event import Context
from event_sourcery.event_sourcing import Repository
from event_sourcery.exceptions import ConcurrentStreamWriteError

from .light_switch import LightSwitch, TurnedOff, TurnedOn


def test_light_switch_aggregate_logs_events() -> None:
    switch = LightSwitch()
    switch.turn_on()
    switch.turn_off()

    with switch.__persisting_changes__() as changes:
        events = list(changes)
    assert len(events) == 2
    assert isinstance(events[0], TurnedOn)
    assert isinstance(events[1], TurnedOff)


def test_light_switch_cannot_be_turned_on_twice() -> None:
    switch = LightSwitch()
    switch.turn_on()

    with pytest.raises(LightSwitch.AlreadyTurnedOn):
        switch.turn_on()


def test_light_switch_cannot_be_turned_off_twice() -> None:
    switch = LightSwitch()
    switch.turn_on()
    switch.turn_off()

    with pytest.raises(LightSwitch.AlreadyTurnedOff):
        switch.turn_off()


def test_light_switch_changes_are_preserved_by_repository(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        try:
            wrapped.aggregate.turn_on()
        except LightSwitch.AlreadyTurnedOn:
            # o mon Dieu, I made a mistake!
            wrapped.aggregate.turn_off()


def test_nothing_when_no_changes_on_aggregate(
    repo: Repository[LightSwitch],
    event_store: EventStore,
) -> None:
    uuid = StreamUUID()
    with repo.aggregate(uuid, LightSwitch()):
        pass

    stream = event_store.load_stream(StreamId(uuid, category=LightSwitch.category))
    assert list(stream) == []


def test_repository_supports_optimistic_locking(
    repo: Repository[LightSwitch],
) -> None:
    uuid = StreamUUID(uuid4())
    with repo.aggregate(uuid, LightSwitch()) as wrapped:
        wrapped.aggregate.turn_on()

    with pytest.raises(ConcurrentStreamWriteError):
        with repo.aggregate(uuid, LightSwitch()) as second:
            with repo.aggregate(uuid, LightSwitch()) as third:
                second.aggregate.turn_off()
                third.aggregate.turn_off()

    assert not second.aggregate.shines


def test_context_is_attached_to_events_saved_by_repository(
    repo: Repository[LightSwitch],
    event_store: EventStore,
) -> None:
    class RequestContext(Context):
        user_id: str

    uuid = StreamUUID(uuid4())
    ctx = RequestContext(user_id="user-123")
    with repo.aggregate(uuid, LightSwitch(), context=ctx) as wrapped:
        wrapped.aggregate.turn_on()

    stream_id = StreamId(uuid, category=LightSwitch.category)
    events = list(event_store.load_stream(stream_id))
    assert len(events) == 1
    loaded_ctx = events[0].get_context(RequestContext)
    assert loaded_ctx.user_id == "user-123"

from uuid import uuid4

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store.backend import Backend
from event_sourcery.event_store.exceptions import (
    AnotherStreamWithThisNameButOtherIdExists,
    IllegalCategoryName,
)
from event_sourcery.event_store.stream import StreamId
from tests.bdd import Given, Then, When
from tests.factories import AnEvent


def test_can_append_then_load_with_named_stream(given: Given, then: Then) -> None:
    given.stream(stream_id := StreamId(name="Test #1"))
    given.event(an_event := AnEvent(), on=stream_id)
    then.stream(stream_id).loads([an_event])


def test_can_append_then_load_with_named_stream_with_assigned_uuid(
    given: Given,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId(name="Test #2"))
    given.event(an_event := AnEvent(), on=stream_id)
    then.stream(stream_id).loads([an_event])
    then.stream(StreamId(name="Test #2")).loads([an_event])


@pytest.mark.skip_backend(backend="kurrentdb", reason="KurrentDB can't use both ids")
def test_lets_appending_by_both_id_and_name_then_just_name(
    given: Given,
    then: Then,
) -> None:
    given.stream(stream_id := StreamId(name="Test #3"))
    given.event(stored_by_id := AnEvent(), on=stream_id)
    given.event(stored_by_name := AnEvent(), on=StreamId(name="Test #3"))
    then.stream(stream_id).loads([stored_by_id, stored_by_name])
    then.stream(StreamId(name="Test #3")).loads([stored_by_id, stored_by_name])


@pytest.mark.skip_backend(
    backend=["kurrentdb_backend", "in_memory_backend"],
    reason="Can't use both ids",
)
def test_blocks_new_stream_uuid_with_same_name_as_other(
    given: Given,
    when: When,
) -> None:
    class CorruptedStreamId(StreamId):
        NAMESPACE = uuid4()

    given.stream(stream_id := StreamId(name="Test #4"))
    given.event(AnEvent(), on=stream_id)
    with pytest.raises(AnotherStreamWithThisNameButOtherIdExists):
        when.appends(AnEvent(), to=CorruptedStreamId(name="Test #4"))


def test_kurrentdb_cant_use_category_with_dash(
    kurrentdb_backend: Backend,
    request: SubRequest,
) -> None:
    when = When(kurrentdb_backend, request)

    with pytest.raises(IllegalCategoryName):
        when.appends(AnEvent(), to=StreamId(category="with-dash"))

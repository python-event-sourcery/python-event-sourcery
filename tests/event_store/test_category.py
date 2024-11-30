from uuid import UUID, uuid4

import pytest

from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.factories import AnEvent
from tests.matchers import any_wrapped_event


@pytest.mark.parametrize(
    ["stream_id"],
    [
        (StreamId(name="Test #1", category="test"),),
        (StreamId(uuid=uuid4(), category="test"),),
    ],
    ids=["by_name", "by_uuid"],
)
def test_can_append_and_load_with_category(
    given: Given,
    then: Then,
    stream_id: StreamId,
) -> None:
    given.event(an_event := AnEvent(), on=stream_id)
    then.stream(stream_id).loads_only([any_wrapped_event(an_event)])


@pytest.mark.parametrize(
    ["stream_1", "stream_2"],
    [
        (
            StreamId(name="Same name", category="c1"),
            StreamId(name="Same name", category="c2"),
        ),
        (
            StreamId(uuid=UUID("48188c14-52ba-4ed0-8477-6012d3d9aab1"), category="c1"),
            StreamId(uuid=UUID("48188c14-52ba-4ed0-8477-6012d3d9aab1"), category="c2"),
        ),
    ],
    ids=["by_name", "by_uuid"],
)
def test_different_streams_when_same_name_but_different_category(
    given: Given,
    then: Then,
    stream_1: StreamId,
    stream_2: StreamId,
) -> None:
    given.event(an_event := AnEvent(), on=stream_1)
    given.event(an_event, on=stream_2)

    then.stream(stream_1).loads_only([any_wrapped_event(an_event)])
    then.stream(stream_2).loads_only([any_wrapped_event(an_event)])
    assert then.stream(stream_1).events != then.stream(stream_2).events


def test_removes_stream_with_category(given: Given, when: When, then: Then) -> None:
    given.stream(stream_1 := StreamId(name="name", category="c1"))
    given.stream(stream_2 := StreamId(name="name", category="c2"))
    given.event(an_event := AnEvent(), on=stream_1)
    given.event(an_event, on=stream_2)

    when.deletes(stream_1)

    then.stream(stream_1).is_empty()
    then.stream(stream_2).loads_only([any_wrapped_event(an_event)])

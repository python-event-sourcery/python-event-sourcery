from event_sourcery import StreamId
from tests.event_store.bdd import Given, Then, When
from tests.event_store.factories import AnEvent


def test_removes_stream(given: Given, then: Then, when: When) -> None:
    given.stream(stream := StreamId())
    given.event(AnEvent(), on=stream)
    when.deletes(stream)
    then.stream(stream).is_empty()

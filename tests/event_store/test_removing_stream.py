from event_sourcery.event_store import StreamId
from tests.bdd import Given, Then, When
from tests.factories import AnEvent


def test_removes_stream(given: Given, then: Then, when: When) -> None:
    given.stream(stream := StreamId())
    given.event(AnEvent(), on=stream)
    when.deletes(stream)
    then.stream(stream).is_empty()

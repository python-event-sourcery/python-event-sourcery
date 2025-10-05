from event_sourcery.event_store.types import StreamId
from tests.bdd import Given, Then, When
from tests.factories import an_event


def test_removes_stream(given: Given, then: Then, when: When) -> None:
    given.stream(stream := StreamId())
    given.event(an_event(), on=stream)
    when.deletes(stream)
    then.stream(stream).is_empty()


def test_nothing_when_removing_not_existing_stream(then: Then, when: When) -> None:
    when.deletes(stream := StreamId(name="Not existing"))
    then.stream(stream).is_empty()

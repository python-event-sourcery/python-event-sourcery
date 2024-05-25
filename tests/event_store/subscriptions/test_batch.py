import pytest

from tests.bdd import Given, Then, When
from tests.factories import an_event
from tests.matchers import any_record


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_receives_requested_batch_size(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.batch_subscription(of_size=2)
    when.stream().receives(first := an_event(), second := an_event(), an_event())
    then(subscription).next_batch_is([any_record(first), any_record(second)])


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_returns_smaller_batch_when_timelimit_hits(
    given: Given,
    when: When,
    then: Then,
) -> None:
    timebox = given.expected_execution(seconds=1)
    subscription = given.batch_subscription(of_size=2, timelimit=1)

    when.stream().receives(event := an_event())

    with timebox:
        then(subscription).next_batch_is([any_record(event)])


@pytest.mark.not_implemented(
    backend=["sqlalchemy_sqlite", "sqlalchemy_postgres"],
)
def test_subscription_continuously_awaits_for_new_events(
    given: Given,
    when: When,
    then: Then,
) -> None:
    subscription = given.batch_subscription(of_size=2)

    when.stream().receives(
        first := an_event(),
        second := an_event(),
        third := an_event(),
    )
    then(subscription).next_batch_is([any_record(first), any_record(second)])

    when.stream().receives(fourth := an_event(), fifth := an_event())
    then(subscription).next_batch_is([any_record(third), any_record(fourth)])
    then(subscription).next_batch_is([any_record(fifth)])
    then(subscription).next_batch_is_empty()

    when.stream().receives(sixth := an_event(), seventh := an_event())
    then(subscription).next_batch_is([any_record(sixth), any_record(seventh)])
    then(subscription).next_batch_is_empty()
    then(subscription).next_batch_is_empty()

import pytest

from tests.events import BaseEvent


def test_detects_duplicated_events_class_names() -> None:
    class EventToBeDuplicated(BaseEvent):
        pass

    with pytest.raises(Exception):

        class EventToBeDuplicated(BaseEvent):  # type: ignore  # noqa: F811
            last_name: str

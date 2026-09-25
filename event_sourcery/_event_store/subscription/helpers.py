from datetime import timedelta

from event_sourcery._event_store.subscription.interfaces import Seconds


def to_timedelta(timelimit: Seconds | timedelta) -> timedelta:
    seconds = (
        timelimit if isinstance(timelimit, timedelta) else timedelta(seconds=timelimit)
    )
    if seconds.total_seconds() < 0.1:
        raise ValueError(
            f"Timebox must be at least 100 milliseconds. Received: "
            f"{seconds.total_seconds():.02f}",
        )
    return seconds

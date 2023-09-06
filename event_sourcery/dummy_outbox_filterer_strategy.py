from event_sourcery.dto import RawEvent


def dummy_filterer(entry: RawEvent) -> bool:
    return True

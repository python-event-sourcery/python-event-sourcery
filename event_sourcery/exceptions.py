class EventStoreException(Exception):
    pass


class NotFound(EventStoreException):
    pass


class NoEventsToAppend(EventStoreException):
    pass


class ConcurrentStreamWriteError(EventStoreException):
    pass

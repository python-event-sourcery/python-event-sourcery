from dataclasses import dataclass
from uuid import UUID


class EventStoreException(Exception):
    pass


class ConcurrentStreamWriteError(EventStoreException):
    pass


class AnotherStreamWithThisNameButOtherIdExists(EventStoreException):
    pass


class IllegalCategoryName(EventStoreException):
    pass


class VersioningMismatch(EventStoreException):
    pass


class ExpectedVersionUsedOnVersionlessStream(VersioningMismatch):
    pass


class NoExpectedVersionGivenOnVersionedStream(VersioningMismatch):
    pass


@dataclass
class IncompatibleUuidAndName(EventStoreException):
    received: UUID
    expected: UUID
    name: str


class ClassModuleUnavailable(Exception):
    pass


class DuplicatedEvent(Exception):
    pass

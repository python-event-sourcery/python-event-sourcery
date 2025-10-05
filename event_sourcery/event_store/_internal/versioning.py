import abc

from event_sourcery.event_store.exceptions import (
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)


class Versioning(abc.ABC):
    @abc.abstractmethod
    def validate_if_compatible(self, version: int | None) -> None:
        pass

    @property
    @abc.abstractmethod
    def initial_version(self) -> int | None:
        pass

    @property
    @abc.abstractmethod
    def expected_version(self) -> int | None:
        pass


class NoVersioning(Versioning):
    def validate_if_compatible(self, version: int | None) -> None:
        if version is not None:
            raise NoExpectedVersionGivenOnVersionedStream

    @property
    def initial_version(self) -> int | None:
        return None

    @property
    def expected_version(self) -> int | None:
        return None


class ExplicitVersioning(Versioning):
    def __init__(self, expected_version: int, initial_version: int) -> None:
        self._expected_version = expected_version
        self._initial_version = initial_version

    def validate_if_compatible(self, version: int | None) -> None:
        if version is None:
            raise ExpectedVersionUsedOnVersionlessStream

    @property
    def initial_version(self) -> int | None:
        return self._initial_version

    @property
    def expected_version(self) -> int | None:
        return self._expected_version


NO_VERSIONING = NoVersioning()

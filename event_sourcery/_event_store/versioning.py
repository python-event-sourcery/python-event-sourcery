import abc

from event_sourcery.exceptions import (
    ExpectedVersionUsedOnVersionlessStream,
    NoExpectedVersionGivenOnVersionedStream,
)


class Versioning(abc.ABC):
    """
    Abstract base class for versioning strategies in event streams.

    Defines the contract for handling optimistic concurrency control in event sourcing.
    Implementations determine how expected and initial versions are managed and
    validated when appending events to a stream.
    """

    @abc.abstractmethod
    def validate_if_compatible(self, version: int | None) -> None:
        """
        Validates if the provided version is compatible with the versioning strategy.

        Used to enforce optimistic concurrency control.
        Implementations should raise an exception if the version is not compatible.

        Args:
            version (int | None): The version to validate (may be None).

        Raises:
            Exception: If the version is not compatible with the strategy.
        """
        pass

    @property
    @abc.abstractmethod
    def initial_version(self) -> int | None:
        """
        Returns the initial version to assign to the first event in a batch.

        Returns:
            int | None: The initial version, or None if not applicable.
        """
        pass

    @property
    @abc.abstractmethod
    def expected_version(self) -> int | None:
        """
        Returns the expected version for optimistic concurrency control.

        Returns:
            int | None: The expected version, or None if not applicable.
        """
        pass


class NoVersioning(Versioning):
    """
    Versioning strategy for streams that do not use versioning.

    Used for streams where optimistic concurrency control is not required. Any attempt
    to provide an expected version will result in an error.
    """

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
    """
    Versioning strategy that requires explicit expected and initial versions.

    Used for streams with optimistic concurrency control. Ensures that the expected
    version is provided and validated when appending events, and that the initial
    version is tracked.

    Args:
        expected_version (int): The version expected by the caller.
        initial_version (int): The initial version of the first event in the batch.
    """

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

import pytest

from event_sourcery.backend import Backend
from event_sourcery.event_sourcing import AsyncRepository, Repository
from tests.adapter import BackendFacade, RepositoryFacade
from tests.backend.django import django_backend  # noqa: F401
from tests.backend.in_memory import in_memory_backend  # noqa: F401
from tests.backend.in_memory_async import in_memory_async_backend  # noqa: F401
from tests.backend.kurrentdb import kurrentdb_backend  # noqa: F401
from tests.backend.kurrentdb_async import kurrentdb_async_backend  # noqa: F401
from tests.backend.sqlalchemy import (  # noqa: F401
    sqlalchemy_postgres_backend,
    sqlalchemy_sqlite_backend,
)
from tests.backend.sqlalchemy_async import (  # noqa: F401
    sqlalchemy_async_postgres_backend,
    sqlalchemy_async_sqlite_backend,
)
from tests.event_sourcing.light_switch import LightSwitch
from tests.event_store.conftest import backend, selected_backends  # noqa: F401


@pytest.fixture()
def repo(
    backend: Backend,  # noqa: F811
) -> Repository[LightSwitch] | RepositoryFacade[LightSwitch]:
    if isinstance(backend, BackendFacade):
        return RepositoryFacade(
            AsyncRepository[LightSwitch](backend._async.event_store),
            backend.runner,
        )
    return Repository[LightSwitch](backend.event_store)

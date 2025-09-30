from typing import cast

import pytest
from _pytest.fixtures import SubRequest

from event_sourcery.event_store import Backend
from tests import mark
from tests.backend.django import django
from tests.backend.in_memory import in_memory
from tests.backend.kurrentdb import kurrentdb
from tests.backend.sqlalchemy import sqlalchemy_postgres, sqlalchemy_sqlite


@pytest.fixture(
    params=[
        django,
        kurrentdb,
        in_memory,
        sqlalchemy_sqlite,
        sqlalchemy_postgres,
    ]
)
def backend(request: SubRequest) -> Backend:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)
    return cast(Backend, request.getfixturevalue(backend_name))

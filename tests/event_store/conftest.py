from contextlib import nullcontext
from typing import Callable, ContextManager, Iterator, cast

import pytest
from _pytest.fixtures import SubRequest
from django.db import transaction as django_transaction

from event_sourcery.event_store import BackendFactory
from event_sourcery_django import DjangoBackendFactory
from tests import mark
from tests.backend.django import django
from tests.backend.esdb import esdb
from tests.backend.in_memory import in_memory
from tests.backend.sqlalchemy import sqlalchemy_postgres, sqlalchemy_sqlite
from tests.event_store.other_client import OtherClient


@pytest.fixture(
    params=[
        django,
        esdb,
        in_memory,
        sqlalchemy_sqlite,
        sqlalchemy_postgres,
    ]
)
def event_store_factory(request: SubRequest) -> BackendFactory:
    backend_name: str = request.param.__name__
    mark.xfail_if_not_implemented_yet(request, backend_name)
    mark.skip_backend(request, backend_name)
    return cast(BackendFactory, request.getfixturevalue(backend_name))


@pytest.fixture
def other_client(event_store_factory: BackendFactory) -> Iterator[OtherClient]:
    transaction_ctx: Callable[[], ContextManager]
    if isinstance(event_store_factory, DjangoBackendFactory):
        transaction_ctx = django_transaction.atomic
    else:
        # TODO: SQLALchemy should pass session.begin() or equivalent
        transaction_ctx = nullcontext

    client = OtherClient(event_store_factory, transaction_ctx)
    yield client
    client.stop()

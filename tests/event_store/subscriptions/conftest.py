from contextlib import nullcontext
from typing import Callable, ContextManager, Iterator

import pytest
from django.db import transaction as django_transaction

from event_sourcery.event_store import BackendFactory
from event_sourcery_django import DjangoBackendFactory
from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory
from tests.event_store.subscriptions.other_client import OtherClient


@pytest.fixture
def other_client(
    other_client_event_store_factory: BackendFactory,
) -> Iterator[OtherClient]:
    transaction_ctx: Callable[[], ContextManager]
    match other_client_event_store_factory:
        case DjangoBackendFactory():
            transaction_ctx = django_transaction.atomic
        case SQLAlchemyBackendFactory(_session=session):
            transaction_ctx = session.begin
        case _:
            transaction_ctx = nullcontext

    client = OtherClient(other_client_event_store_factory, transaction_ctx)
    yield client
    client.stop()

from contextlib import nullcontext
from typing import Callable, ContextManager, Iterator

import pytest
from django.db import transaction as django_transaction

from event_sourcery.event_store import BackendFactory
from event_sourcery_django import DjangoBackendFactory
from tests.event_store.subscriptions.other_client import OtherClient


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

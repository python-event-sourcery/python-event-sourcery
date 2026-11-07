from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

import django as django_framework
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

APP = "event_sourcery_django"
BEFORE = [(APP, "0001_initial")]
UNIQUE_VERSIONS = [(APP, "0002_remove_event_ix_events_stream_id_version_and_more")]


@pytest.fixture()
def executor(transactional_db: None) -> Iterator[MigrationExecutor]:
    django_framework.setup()
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    yield executor
    executor.loader.project_state(BEFORE).apps.get_model(
        APP, "Stream"
    ).objects.all().delete()
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes(APP))


def _insert_events(executor: MigrationExecutor, versions: list[int | None]) -> str:
    apps = executor.loader.project_state(BEFORE).apps
    stream = apps.get_model(APP, "Stream").objects.create(
        uuid=uuid4(), name=None, category="", version=None, tenant_id="default"
    )
    for version in versions:
        apps.get_model(APP, "Event").objects.create(
            uuid=uuid4(),
            version=version,
            name="AnEvent",
            data={},
            event_context={},
            created_at=datetime.now(tz=timezone.utc),
            stream=stream,
        )
    return str(stream.uuid)


def _migrate_to_unique_versions(executor: MigrationExecutor) -> None:
    executor.loader.build_graph()
    executor.migrate(UNIQUE_VERSIONS)


def test_unique_versions_migration_explains_duplicated_versions(
    executor: MigrationExecutor,
) -> None:
    stream_uuid = _insert_events(executor, [1, 1, 2])

    with pytest.raises(RuntimeError) as error:
        _migrate_to_unique_versions(executor)

    message = str(error.value)
    assert "1 duplicated (stream, version) pair" in message
    assert f"stream {stream_uuid} version 1" in message
    assert "CHANGELOG" in message


def test_unique_versions_migration_passes_without_duplicates(
    executor: MigrationExecutor,
) -> None:
    _insert_events(executor, [1, 2, None, None])

    _migrate_to_unique_versions(executor)

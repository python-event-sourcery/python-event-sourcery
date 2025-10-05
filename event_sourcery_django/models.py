from typing import ClassVar
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from event_sourcery.event_store.types import StreamId, TenantId


class StreamManager(models.Manager):
    def by_stream_id(self, stream_id: StreamId, tenant_id: TenantId) -> models.QuerySet:
        category = stream_id.category or ""
        condition = models.Q(uuid=stream_id, category=category, tenant_id=tenant_id)
        if stream_id.name:
            condition = condition | models.Q(
                name=stream_id.name,
                category=category,
                tenant_id=tenant_id,
            )
        return self.filter(condition)


class Stream(models.Model):
    DoesNotExist: ClassVar[ObjectDoesNotExist]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=255, default="")
    tenant_id = models.CharField(max_length=255)
    version = models.BigIntegerField(null=True, blank=True)

    objects = StreamManager()

    class Meta:
        unique_together = (
            ("uuid", "category", "tenant_id"),
            ("name", "category", "tenant_id"),
        )


class Event(models.Model):
    objects: models.Manager

    id = models.BigAutoField(primary_key=True)
    version = models.IntegerField(null=True, blank=True)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    data = models.JSONField()
    event_context = models.JSONField()
    created_at = models.DateTimeField()
    stream = models.ForeignKey(Stream, related_name="events", on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(
                fields=["stream", "version"], name="ix_events_stream_id_version"
            ),
        ]


class Snapshot(models.Model):
    objects: models.Manager

    uuid = models.UUIDField(primary_key=True)
    version = models.IntegerField()
    stream = models.ForeignKey(
        Stream,
        related_name="snapshots",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=50)
    data = models.JSONField()
    event_context = models.JSONField()
    created_at = models.DateTimeField()


class OutboxEntry(models.Model):
    objects: models.Manager

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    data = models.JSONField()
    stream_name = models.CharField(max_length=255, null=True, blank=True)
    position = models.BigIntegerField()
    tries_left = models.IntegerField()

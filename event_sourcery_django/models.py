from uuid import uuid4

from django.db import models


class Stream(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=255, default="")
    version = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = (
            ("uuid", "category"),
            ("name", "category"),
        )


class Event(models.Model):
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
            models.Index(fields=["stream", "version"], name="ix_events_stream_id_version"),
        ]


class Snapshot(models.Model):
    uuid = models.UUIDField(primary_key=True)
    version = models.IntegerField()
    stream = models.ForeignKey(Stream, related_name="snapshots", on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    data = models.JSONField()
    event_context = models.JSONField()
    created_at = models.DateTimeField()


class OutboxEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    data = models.JSONField()
    stream_name = models.CharField(max_length=255, null=True, blank=True)
    tries_left = models.IntegerField(default=3)


class ProjectorCursor(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    stream_id = models.UUIDField()
    category = models.CharField(max_length=255, null=True, blank=True)
    version = models.BigIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=["name", "stream_id", "category"], name="ix_name_stream_id"),
        ]

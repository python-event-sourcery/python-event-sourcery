from pathlib import Path

import django as django_framework
import pytest
from _pytest.fixtures import SubRequest
from django.core.management import call_command as django_command

from event_sourcery_django import DjangoBackendFactory

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "es_django",
        "USER": "es",
        "PASSWORD": "es",
        "HOST": "localhost",
        "PORT": "5432",
    },
}
INSTALLED_APPS: list[str] = ["event_sourcery_django"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


@pytest.fixture()
def django(transactional_db: None, request: SubRequest) -> DjangoBackendFactory:
    django_framework.setup()
    django_command("migrate")
    return DjangoBackendFactory()

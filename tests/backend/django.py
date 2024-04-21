from pathlib import Path

import django as django_framework
import pytest
from _pytest.fixtures import SubRequest
from django.core.management import call_command as django_command

from event_sourcery_django import DjangoBackendFactory
from tests.mark import xfail_if_not_implemented_yet

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
    skip_django = request.node.get_closest_marker("skip_django")
    if skip_django:
        reason = skip_django.kwargs.get("reason", "")
        pytest.skip(f"Skipping Django tests: {reason}")

    xfail_if_not_implemented_yet(request, "django")
    return DjangoBackendFactory()

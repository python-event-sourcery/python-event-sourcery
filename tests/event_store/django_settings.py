from pathlib import Path

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

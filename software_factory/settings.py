import os
from pathlib import Path


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "calculator",
    "factory.apps.FactoryConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "software_factory.middleware.NoStoreMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "software_factory.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "software_factory.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FACTORY_STATUS_BACKEND = os.environ.get("FACTORY_STATUS_BACKEND", "file")
FACTORY_STATUS_FILE = Path(os.environ.get("FACTORY_STATUS_FILE", BASE_DIR / "factory_status.json"))
FACTORY_STATUS_BUCKET = os.environ.get("FACTORY_STATUS_BUCKET", "")
FACTORY_STATUS_KEY = os.environ.get("FACTORY_STATUS_KEY", "factory/status.json")
FACTORY_RUNS_DIR = Path(os.environ.get("FACTORY_RUNS_DIR", BASE_DIR / "factory_runs"))
FACTORY_RUNNER_BACKEND = os.environ.get("FACTORY_RUNNER_BACKEND", "local")
FACTORY_ECS_CLUSTER = os.environ.get("FACTORY_ECS_CLUSTER", "")
FACTORY_ECS_TASK_DEFINITION = os.environ.get("FACTORY_ECS_TASK_DEFINITION", "")
FACTORY_ECS_SUBNETS = env_list("FACTORY_ECS_SUBNETS", [])
FACTORY_ECS_ASSIGN_PUBLIC_IP = os.environ.get("FACTORY_ECS_ASSIGN_PUBLIC_IP", "ENABLED")
FACTORY_WORKER_CONTAINER_NAME = os.environ.get("FACTORY_WORKER_CONTAINER_NAME", "worker")


DEMO_EPOCH_FILE = Path(os.environ.get("DEMO_EPOCH_FILE", BASE_DIR / "demo_epoch.txt"))

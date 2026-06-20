import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from backend.observability import configure_sentry

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


def env_required(name, default=""):
    value = os.getenv(name, default)

    if IS_DEPLOYED and not value:
        raise ImproperlyConfigured(f"{name} is required in deployed environments.")

    return value


def normalize_url_path(value):
    normalized = value.strip().strip("/")
    if not normalized:
        return ""
    return f"{normalized}/"


DJANGO_ENVIRONMENT = os.getenv("DJANGO_ENVIRONMENT", "development").lower()
IS_PRODUCTION = DJANGO_ENVIRONMENT == "production"
IS_DEPLOYED = DJANGO_ENVIRONMENT in {"production", "staging"}

DEBUG = env_bool("DJANGO_DEBUG", not IS_DEPLOYED)
SECRET_KEY = env_required("DJANGO_SECRET_KEY", "development-only-secret-key")
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "" if IS_DEPLOYED else "127.0.0.1,localhost,192.168.1.19,10.10.3.189,10.50.48.251",
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
DJANGO_ADMIN_ENABLED = env_bool("DJANGO_ADMIN_ENABLED", not IS_DEPLOYED)
DJANGO_ADMIN_PATH = normalize_url_path(os.getenv("DJANGO_ADMIN_PATH", "admin/"))

if IS_DEPLOYED:
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG must be false in deployed environments.")

    if (
            SECRET_KEY == "development-only-secret-key"
            or len(SECRET_KEY) < 50
            or len(set(SECRET_KEY)) < 8
    ):
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a strong production secret.")

    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in deployed environments.")

    if DJANGO_ADMIN_ENABLED and DJANGO_ADMIN_PATH == "admin/":
        raise ImproperlyConfigured(
            "DJANGO_ADMIN_PATH must not be admin/ when admin is enabled in deployed environments."
        )

if DJANGO_ADMIN_ENABLED and not DJANGO_ADMIN_PATH:
    raise ImproperlyConfigured("DJANGO_ADMIN_PATH is required when admin is enabled.")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    'accounts.apps.AccountsConfig',
    'hostels',
    'bookings.apps.BookingsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'backend.middleware.RequestIdMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'room_booking'),
        'USER': os.getenv('DB_USER', 'roomuser'),
        'PASSWORD': env_required('DB_PASSWORD', 'root'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

if IS_DEPLOYED and DATABASES["default"]["PASSWORD"] in {"", "root", "password"}:
    raise ImproperlyConfigured("DB_PASSWORD must be set to a strong deployed password.")

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', '')
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '240'))
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '300'))

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', IS_DEPLOYED)
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', IS_DEPLOYED)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', IS_DEPLOYED)
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '31536000' if IS_DEPLOYED else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("DJANGO_LOG_FORMAT", "json" if IS_DEPLOYED else "console")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "backend.logging_utils.RequestIdFilter",
        },
    },
    "formatters": {
        "console": {
            "format": "%(levelname)s %(asctime)s %(name)s request_id=%(request_id)s %(message)s",
        },
        "json": {
            "()": "backend.logging_utils.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "json" if LOG_FORMAT == "json" else "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "backend": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "bookings": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "hostels": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

configure_sentry(DJANGO_ENVIRONMENT)

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "backend.exceptions.custom_exception_handler",

    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],

    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/min",
        "availability": "120/min",
        "booking_read": "120/min",
        "booking_mutation": "30/min",
    },

    "DEFAULT_PAGINATION_CLASS": "backend.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 5,
}

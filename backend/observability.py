import logging
import os

from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger(__name__)


def configure_sentry(environment):
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as exc:
        raise ImproperlyConfigured(
            "SENTRY_DSN is set, but sentry-sdk is not installed."
        ) from exc

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", environment),
        release=os.getenv("SENTRY_RELEASE") or None,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(event_level=logging.ERROR),
        ],
        send_default_pii=False,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
    )
    logger.info("sentry_configured")

import logging

from celery import shared_task
from django.core.exceptions import ImproperlyConfigured
from django.db import close_old_connections

from bookings.services.google_sheet_sync import fill_visitor_names_in_calendar


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
    dont_autoretry_for=(ImproperlyConfigured,),
    acks_late=True,
)
def sync_google_sheet_calendar(self):
    close_old_connections()

    try:
        result = fill_visitor_names_in_calendar()
        logger.info("Google Sheet calendar sync completed: %s", result)
        return result

    finally:
        close_old_connections()

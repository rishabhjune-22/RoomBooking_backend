from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from backend.views import health_check

urlpatterns = [
    path('health/', health_check, name='health-check'),

    # Public APIs
    path('api/auth/', include('accounts.urls')),
    path('api/', include('hostels.urls')),
    path('api/', include('bookings.urls')),
]

if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.append(path(settings.DJANGO_ADMIN_PATH, admin.site.urls))

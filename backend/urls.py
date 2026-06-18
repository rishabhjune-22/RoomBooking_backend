from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public APIs
    path('api/', include('hostels.urls')),
    path('api/', include('bookings.urls')),
]
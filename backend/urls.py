from django.contrib import admin
from django.urls import path, include
from accounts.views import MyTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # your apps
    path('api/accounts/', include('accounts.urls')),
    path('api/', include('hostels.urls')),
    path('api/', include('bookings.urls')),
]
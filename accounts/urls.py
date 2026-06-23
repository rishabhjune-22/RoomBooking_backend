from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, SignupView
from .views import AdminLoginView, AdminSignupView, RequesterLoginView, RequesterSignupView


class PublicTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []


urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("admin/signup/", AdminSignupView.as_view(), name="auth-admin-signup"),
    path("admin/login/", AdminLoginView.as_view(), name="auth-admin-login"),
    path("requester/signup/", RequesterSignupView.as_view(), name="auth-requester-signup"),
    path("requester/login/", RequesterLoginView.as_view(), name="auth-requester-login"),
    path("token/refresh/", PublicTokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]

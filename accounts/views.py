from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from backend.responses import api_error, api_success, serializer_error_response

from .serializers import (
    AuthUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    SignupSerializer,
)


def auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "user": AuthUserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_error_response(serializer, "Account could not be created.")

        user = serializer.save()
        return api_success(
            "Account created successfully.",
            auth_payload(user),
            status_code=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return serializer_error_response(serializer, "Invalid email or password.")

        return api_success(
            "Login successful.",
            auth_payload(serializer.validated_data["user"]),
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(
            "User fetched successfully.",
            AuthUserSerializer(request.user).data,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_error_response(serializer, "Logout failed.")

        refresh_token = serializer.validated_data.get("refresh")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except AttributeError:
                pass
            except TokenError:
                return api_error(
                    "Invalid refresh token.",
                    errors={"refresh": ["Invalid refresh token."]},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        return api_success("Logged out successfully.", None)

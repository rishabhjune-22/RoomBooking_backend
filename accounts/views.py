from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import SignupSerializer
from .throttles import LoginRateThrottle, SignupRateThrottle
from .token_serializers import MyTokenObtainPairSerializer


@api_view(["POST"])
@throttle_classes([SignupRateThrottle])
def signup(request):
    serializer = SignupSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                "success": True,
                "message": "User created successfully",
                "data": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {
            "success": False,
            "message": "Signup failed",
            "errors": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get("refresh")

    if not refresh_token:
        return Response(
            {
                "success": False,
                "message": "Refresh token is required",
                "errors": {
                    "refresh": ["This field is required."]
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(
            {
                "success": True,
                "message": "Logged out successfully",
                "data": None,
            },
            status=status.HTTP_200_OK,
        )
    except TokenError:
        return Response(
            {
                "success": False,
                "message": "Invalid or expired refresh token",
                "errors": {
                    "refresh": ["Invalid or expired token."]
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        return Response(
            {
                "success": False,
                "message": "Internal server error",
                "errors": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]



@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([LoginRateThrottle])
def encryption_material(request):
    user = request.user

    if not user.encrypted_dek or not user.dek_wrap_nonce or not user.kdf_metadata:
        return Response(
            {
                "success": False,
                "message": "Encryption material not configured",
                "errors": {
                    "encryption": ["Encryption material not found for this user."]
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "success": True,
            "message": "Encryption material fetched successfully",
            "data": {
                "encrypted_dek": user.encrypted_dek,
                "dek_wrap_nonce": user.dek_wrap_nonce,
                "kdf_metadata": user.kdf_metadata,
            },
        },
        status=status.HTTP_200_OK,
    )    
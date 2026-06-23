from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone

from backend.responses import api_error, api_success, serializer_error_response

from .models import UserProfile
from .permissions import IsAdminOrSuperAdminRole, IsApprovedUser, IsSuperAdminRole
from .serializers import (
    AccountApprovalActionSerializer,
    AccountRequestSerializer,
    AuthUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    SignupSerializer,
)
from .roles import (
    APPROVAL_APPROVED,
    APPROVAL_REJECTED,
    ROLE_ADMIN,
    ROLE_REQUESTER,
    ROLE_SUPERADMIN,
    get_user_profile,
)


def auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "user": AuthUserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def signup_payload(user):
    return {"user": AuthUserSerializer(user).data}


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    role = None

    def post(self, request):
        serializer = SignupSerializer(data=request.data, role=self.role)
        if not serializer.is_valid():
            return serializer_error_response(serializer, "Account could not be created.")

        user = serializer.save()
        profile = get_user_profile(user)
        if profile.role == ROLE_ADMIN:
            message = "Account created successfully. Please wait for superadmin approval."
        else:
            message = "Account created successfully. Please wait for approval."
        return api_success(
            message,
            signup_payload(user),
            status_code=status.HTTP_201_CREATED,
        )


class AdminSignupView(SignupView):
    role = ROLE_ADMIN


class RequesterSignupView(SignupView):
    role = ROLE_REQUESTER


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    expected_role = None

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={
                "request": request,
                "expected_role": self.expected_role,
            },
        )
        if not serializer.is_valid():
            message = "Invalid email or password."
            non_field_errors = serializer.errors.get("non_field_errors")
            if non_field_errors:
                message = str(non_field_errors[0])
            return serializer_error_response(serializer, message)

        return api_success(
            "Login successful.",
            auth_payload(serializer.validated_data["user"]),
        )


class AdminLoginView(LoginView):
    expected_role = ROLE_ADMIN


class RequesterLoginView(LoginView):
    expected_role = ROLE_REQUESTER


class MeView(APIView):
    permission_classes = [IsApprovedUser]

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


class AccountRequestQueryMixin:
    allowed_roles = ()
    default_role = None

    def get_queryset(self, request):
        queryset = (
            UserProfile.objects
            .select_related("user", "approved_by")
            .exclude(role=ROLE_SUPERADMIN)
            .order_by("-created_at", "-id")
        )
        if self.allowed_roles:
            queryset = queryset.filter(role__in=self.allowed_roles)

        role_filter = request.query_params.get("role") or self.default_role
        if role_filter:
            if self.allowed_roles and role_filter not in self.allowed_roles:
                queryset = queryset.none()
            else:
                queryset = queryset.filter(role=role_filter)

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(approval_status=status_filter)

        return queryset


class SuperadminAccountRequestListView(AccountRequestQueryMixin, APIView):
    permission_classes = [IsSuperAdminRole]
    allowed_roles = (ROLE_ADMIN, ROLE_REQUESTER)

    def get(self, request):
        return api_success(
            "Account requests fetched successfully.",
            AccountRequestSerializer(self.get_queryset(request), many=True).data,
        )


class SuperadminAccountRequestDetailView(AccountRequestQueryMixin, APIView):
    permission_classes = [IsSuperAdminRole]
    allowed_roles = (ROLE_ADMIN, ROLE_REQUESTER)

    def get(self, request, pk):
        profile = self.get_queryset(request).filter(pk=pk).first()
        if profile is None:
            return api_error("Account request not found.", status_code=status.HTTP_404_NOT_FOUND)
        return api_success(
            "Account request fetched successfully.",
            AccountRequestSerializer(profile).data,
        )


class AdminRequesterAccountListView(AccountRequestQueryMixin, APIView):
    permission_classes = [IsAdminOrSuperAdminRole]
    allowed_roles = (ROLE_REQUESTER,)
    default_role = ROLE_REQUESTER

    def get(self, request):
        return api_success(
            "Requester accounts fetched successfully.",
            AccountRequestSerializer(self.get_queryset(request), many=True).data,
        )


class AdminRequesterAccountDetailView(AccountRequestQueryMixin, APIView):
    permission_classes = [IsAdminOrSuperAdminRole]
    allowed_roles = (ROLE_REQUESTER,)
    default_role = ROLE_REQUESTER

    def get(self, request, pk):
        profile = self.get_queryset(request).filter(pk=pk).first()
        if profile is None:
            return api_error("Requester account not found.", status_code=status.HTTP_404_NOT_FOUND)
        return api_success(
            "Requester account fetched successfully.",
            AccountRequestSerializer(profile).data,
        )


class AccountApprovalActionMixin:
    permission_classes = []
    allowed_roles = ()
    not_found_message = "Account request not found."
    success_message = ""

    def get_profile(self, pk):
        queryset = UserProfile.objects.select_for_update().select_related("user", "approved_by")
        if self.allowed_roles:
            queryset = queryset.filter(role__in=self.allowed_roles)
        return queryset.filter(pk=pk).first()

    @transaction.atomic
    def approve_profile(self, request, pk):
        profile = self.get_profile(pk)
        if profile is None:
            return api_error(self.not_found_message, status_code=status.HTTP_404_NOT_FOUND)
        if profile.role == ROLE_SUPERADMIN:
            return api_error("Superadmin accounts cannot be approved here.")

        profile.approval_status = APPROVAL_APPROVED
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.rejection_reason = ""
        profile.user.is_active = True
        profile.user.is_staff = False
        profile.user.is_superuser = False
        profile.user.save(update_fields=["is_active", "is_staff", "is_superuser"])
        profile.save(update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "updated_at",
        ])

        return api_success(self.success_message, AccountRequestSerializer(profile).data)

    @transaction.atomic
    def reject_profile(self, request, pk):
        profile = self.get_profile(pk)
        if profile is None:
            return api_error(self.not_found_message, status_code=status.HTTP_404_NOT_FOUND)
        if profile.role == ROLE_SUPERADMIN:
            return api_error("Superadmin accounts cannot be rejected here.")

        serializer = AccountApprovalActionSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_error_response(serializer, "Account request could not be rejected.")

        remarks = serializer.validated_data.get("remarks", "")
        profile.approval_status = APPROVAL_REJECTED
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        profile.rejection_reason = remarks
        profile.user.is_active = False
        profile.user.is_staff = False
        profile.user.is_superuser = False
        profile.user.save(update_fields=["is_active", "is_staff", "is_superuser"])
        profile.save(update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "updated_at",
        ])

        return api_success(
            "Account rejected successfully.",
            AccountRequestSerializer(profile).data,
        )


class SuperadminAccountRequestApproveView(AccountApprovalActionMixin, APIView):
    permission_classes = [IsSuperAdminRole]
    allowed_roles = (ROLE_ADMIN, ROLE_REQUESTER)
    success_message = "Account approved successfully."

    def post(self, request, pk):
        return self.approve_profile(request, pk)


class SuperadminAccountRequestRejectView(AccountApprovalActionMixin, APIView):
    permission_classes = [IsSuperAdminRole]
    allowed_roles = (ROLE_ADMIN, ROLE_REQUESTER)
    success_message = "Account rejected successfully."

    def post(self, request, pk):
        return self.reject_profile(request, pk)


class AdminRequesterAccountApproveView(AccountApprovalActionMixin, APIView):
    permission_classes = [IsAdminOrSuperAdminRole]
    allowed_roles = (ROLE_REQUESTER,)
    not_found_message = "Requester account not found."
    success_message = "Requester account approved successfully."

    def post(self, request, pk):
        return self.approve_profile(request, pk)


class AdminRequesterAccountRejectView(AccountApprovalActionMixin, APIView):
    permission_classes = [IsAdminOrSuperAdminRole]
    allowed_roles = (ROLE_REQUESTER,)
    not_found_message = "Requester account not found."
    success_message = "Requester account rejected successfully."

    def post(self, request, pk):
        return self.reject_profile(request, pk)

import hashlib

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from backend.responses import api_error, api_success, serializer_error_response
from bookings.models import BookingRequest

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


class WorkflowNotificationCountView(APIView):
    permission_classes = [IsApprovedUser]

    def get(self, request):
        profile = get_user_profile(request.user)
        counts = {
            "booking_requests": 0,
            "requester_accounts": 0,
            "admin_accounts": 0,
            "my_requests": 0,
        }
        items = {
            "booking_requests": [],
            "requester_accounts": [],
            "admin_accounts": [],
            "my_requests": [],
        }

        def marker_for(value):
            return int(value.timestamp()) if value else "none"

        def user_display_name(user):
            return (
                user.get_full_name()
                or user.email
                or user.username
                or "Unknown user"
            )

        def booking_request_fingerprint(booking_request):
            values = [
                booking_request.arrival_at.isoformat() if booking_request.arrival_at else "",
                booking_request.departure_at.isoformat() if booking_request.departure_at else "",
                booking_request.preferred_prefix,
                str(booking_request.preferred_room_id or ""),
                booking_request.room_preference_note,
                booking_request.visitor_name,
                booking_request.visitor_mobile,
                booking_request.visitor_email,
                booking_request.visitor_organisation,
                booking_request.purpose_of_visit,
                booking_request.requestor_name,
                booking_request.requestor_department,
                booking_request.requestor_mobile,
                booking_request.requestor_email,
                booking_request.budget_head_type,
                booking_request.budget_head_value,
                booking_request.budget_head_name,
                booking_request.budget_head_department_name,
                booking_request.budget_head_project_code,
                str(booking_request.attender_required),
                str(booking_request.attender_general_shift),
                str(booking_request.attender_morning_shift),
                str(booking_request.attender_day_shift),
            ]
            return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:12]

        def date_range_text(booking_request):
            arrival_at = timezone.localtime(booking_request.arrival_at)
            departure_at = timezone.localtime(booking_request.departure_at)
            return (
                f"{arrival_at.strftime('%d %b %Y, %I:%M %p')} to "
                f"{departure_at.strftime('%d %b %Y, %I:%M %p')}"
            )

        def booking_request_items(queryset):
            items = []
            for booking_request in queryset:
                requester_name = user_display_name(booking_request.requester)
                room_text = (
                    booking_request.preferred_room.selection_label
                    if booking_request.preferred_room
                    else booking_request.preferred_prefix or "No room preference"
                )
                items.append({
                    "key": (
                        f"booking_request:{booking_request.pk}:"
                        f"{marker_for(booking_request.requested_at)}:"
                        f"{booking_request_fingerprint(booking_request)}"
                    ),
                    "id": booking_request.pk,
                    "title": f"Booking request from {requester_name}",
                    "message": (
                        f"{booking_request.visitor_name or 'Visitor'} requested {room_text} "
                        f"for {date_range_text(booking_request)}."
                    ),
                })
            return items

        def account_items(queryset, prefix, label):
            items = []
            for account_profile in queryset:
                user = account_profile.user
                display_name = user_display_name(user)
                items.append({
                    "key": f"{prefix}:{account_profile.pk}:{marker_for(account_profile.updated_at)}",
                    "id": account_profile.pk,
                    "title": f"{label} approval pending",
                    "message": f"{display_name} ({user.email or user.username}) is waiting for approval.",
                })
            return items

        def reviewed_request_items(queryset):
            titles = {
                BookingRequest.STATUS_APPROVED: "Booking request approved",
                BookingRequest.STATUS_REJECTED: "Booking request rejected",
                BookingRequest.STATUS_CORRECTION_REQUIRED: "Booking request needs correction",
            }
            items = []
            for booking_request in queryset:
                remarks = booking_request.admin_remarks or "No remarks provided."
                items.append({
                    "key": (
                        f"my_request:{booking_request.pk}:{booking_request.status}:"
                        f"{marker_for(booking_request.reviewed_at or booking_request.requested_at)}"
                    ),
                    "id": booking_request.pk,
                    "title": titles.get(booking_request.status, "Booking request reviewed"),
                    "message": (
                        f"{booking_request.visitor_name or 'Your booking request'} was "
                        f"{booking_request.get_status_display().lower()}. Remarks: {remarks}"
                    ),
                })
            return items

        def deleted_request_items(queryset):
            items = []
            for booking_request in queryset:
                deleted_marker = (
                    int(booking_request.deleted_at.timestamp())
                    if booking_request.deleted_at
                    else "deleted"
                )
                remarks = booking_request.delete_reason or "No remarks provided."
                items.append({
                    "key": f"my_request_deleted:{booking_request.pk}:{deleted_marker}",
                    "id": booking_request.pk,
                    "title": "Booking request deleted",
                    "message": (
                        f"Your booking request for "
                        f"{booking_request.visitor_name or 'the selected dates'} was deleted. "
                        f"Remarks: {remarks}"
                    ),
                })
            return items

        if profile.role in {ROLE_ADMIN, ROLE_SUPERADMIN}:
            booking_request_qs = (
                BookingRequest.objects
                .select_related("requester", "preferred_room")
                .filter(
                    status=BookingRequest.STATUS_PENDING,
                    is_deleted=False,
                )
            )
            requester_account_qs = UserProfile.objects.filter(
                role=ROLE_REQUESTER,
                approval_status=UserProfile.APPROVAL_PENDING,
            ).select_related("user")
            items["booking_requests"] = booking_request_items(booking_request_qs)
            items["requester_accounts"] = account_items(
                requester_account_qs,
                "requester_account",
                "Requester account",
            )
            counts["booking_requests"] = len(items["booking_requests"])
            counts["requester_accounts"] = len(items["requester_accounts"])

        if profile.role == ROLE_SUPERADMIN:
            admin_account_qs = UserProfile.objects.filter(
                role=ROLE_ADMIN,
                approval_status=UserProfile.APPROVAL_PENDING,
            ).select_related("user")
            items["admin_accounts"] = account_items(
                admin_account_qs,
                "admin_account",
                "Admin account",
            )
            counts["admin_accounts"] = len(items["admin_accounts"])

        if profile.role == ROLE_REQUESTER:
            my_request_qs = (
                BookingRequest.objects
                .filter(
                    requester=request.user,
                    status__in=[
                        BookingRequest.STATUS_APPROVED,
                        BookingRequest.STATUS_REJECTED,
                        BookingRequest.STATUS_CORRECTION_REQUIRED,
                    ],
                    is_deleted=False,
                )
            )
            deleted_by_admin_qs = (
                BookingRequest.objects
                .filter(requester=request.user, is_deleted=True)
                .exclude(deleted_by=request.user)
                .exclude(deleted_by__isnull=True)
                .order_by("-deleted_at", "-pk")
            )
            items["my_requests"] = (
                reviewed_request_items(my_request_qs)
                + deleted_request_items(deleted_by_admin_qs)
            )
            counts["my_requests"] = len(items["my_requests"])

        counts["total"] = sum(counts.values())
        counts["items"] = items
        return api_success("Workflow notification counts fetched successfully.", counts)


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

    @transaction.atomic
    def delete_profile(self, request, pk):
        profile = self.get_profile(pk)
        if profile is None:
            return api_error(self.not_found_message, status_code=status.HTTP_404_NOT_FOUND)
        if (
                profile.role == ROLE_SUPERADMIN
                or profile.user_id == request.user.id
                or profile.user.is_superuser
        ):
            return api_error("Protected account cannot be deleted.")

        profile_id = profile.pk
        user_id = profile.user_id
        try:
            profile.user.delete()
        except ProtectedError as exc:
            return api_error(
                "Account could not be deleted because related protected data exists.",
                errors={"account": [str(exc)]},
            )

        return api_success(
            "Account deleted successfully.",
            {"id": profile_id, "user_id": user_id},
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


class SuperadminAccountRequestDeleteView(AccountApprovalActionMixin, APIView):
    permission_classes = [IsSuperAdminRole]
    allowed_roles = (ROLE_ADMIN, ROLE_REQUESTER)
    not_found_message = "Account request not found."

    def delete(self, request, pk):
        return self.delete_profile(request, pk)


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

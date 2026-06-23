from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import UserProfile
from .roles import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ROLE_ADMIN,
    ROLE_REQUESTER,
    ROLE_SUPERADMIN,
    get_user_profile,
    set_user_role,
)


User = get_user_model()


def normalize_email(value):
    return User.objects.normalize_email((value or "").strip()).lower()


def user_display_name(user):
    name = user.get_full_name().strip()
    return name or user.email


class AuthUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    remarks = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    mobile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "role",
            "approval_status",
            "remarks",
            "designation",
            "department",
            "mobile",
        ]

    def get_name(self, obj):
        return user_display_name(obj)

    def get_role(self, obj):
        return get_user_profile(obj).role

    def get_approval_status(self, obj):
        return get_user_profile(obj).approval_status

    def get_remarks(self, obj):
        profile = get_user_profile(obj)
        return profile.rejection_reason if profile.approval_status == APPROVAL_REJECTED else ""

    def get_designation(self, obj):
        return get_user_profile(obj).designation

    def get_department(self, obj):
        return get_user_profile(obj).department

    def get_mobile(self, obj):
        return get_user_profile(obj).mobile


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(
        choices=[ROLE_ADMIN, ROLE_REQUESTER],
        required=False,
        default=ROLE_ADMIN,
    )
    admin_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    designation = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    department = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    mobile = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    def __init__(self, *args, **kwargs):
        self.fixed_role = kwargs.pop("role", None)
        super().__init__(*args, **kwargs)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name is required.")
        return name

    def validate_email(self, value):
        email = normalize_email(value)
        if not email:
            raise serializers.ValidationError("Email is required.")

        return email

    def validate(self, attrs):
        if self.fixed_role:
            attrs["role"] = self.fixed_role

        role = attrs.get("role", ROLE_ADMIN)
        if role == ROLE_ADMIN:
            admin_code = (attrs.get("admin_code") or "").strip()
            expected_code = (getattr(settings, "ADMIN_SIGNUP_CODE", "") or "").strip()
            if not expected_code or admin_code != expected_code:
                raise serializers.ValidationError({
                    "admin_code": ["Invalid admin invite code."]
                })

        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })

        if User.objects.filter(
                Q(email__iexact=attrs["email"]) | Q(username__iexact=attrs["email"])
        ).exists():
            raise serializers.ValidationError({
                "email": ["An account with this email already exists."]
            })

        user = User(
            username=attrs["email"],
            email=attrs["email"],
            first_name=attrs["name"],
        )
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["name"],
        )
        set_user_role(
            user,
            validated_data.get("role", ROLE_ADMIN),
            approval_status=APPROVAL_PENDING,
            designation=validated_data.get("designation", ""),
            department=validated_data.get("department", ""),
            mobile=validated_data.get("mobile", ""),
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    expected_role = serializers.ChoiceField(
        choices=[ROLE_ADMIN, ROLE_REQUESTER],
        required=False,
    )

    default_error_messages = {
        "invalid_credentials": _("Invalid email or password."),
    }

    def validate(self, attrs):
        email = normalize_email(attrs.get("email"))
        password = attrs.get("password")
        expected_role = self.context.get("expected_role") or attrs.get("expected_role")

        if not email or not password:
            self.fail("invalid_credentials")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            self.fail("invalid_credentials")

        if not user.check_password(password):
            self.fail("invalid_credentials")

        profile = get_user_profile(user)
        user_role = profile.role
        if expected_role == ROLE_ADMIN and user_role == ROLE_SUPERADMIN:
            pass
        elif expected_role and user_role != expected_role:
            if expected_role == ROLE_ADMIN:
                raise serializers.ValidationError("This account is not an admin account.")
            raise serializers.ValidationError("This account is not a requester account.")

        if profile.approval_status == APPROVAL_PENDING:
            raise serializers.ValidationError("Your account is pending approval.")

        if profile.approval_status == APPROVAL_REJECTED:
            message = "Your account is rejected."
            if profile.rejection_reason:
                message = f"{message} Remarks: {profile.rejection_reason}"
            raise serializers.ValidationError(message)

        if not user.is_active:
            raise serializers.ValidationError("This account is no longer active.")

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        if authenticated_user is None:
            self.fail("invalid_credentials")

        attrs["user"] = authenticated_user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class AccountRequestSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    is_staff = serializers.BooleanField(source="user.is_staff", read_only=True)
    is_superuser = serializers.BooleanField(source="user.is_superuser", read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    remarks = serializers.CharField(source="rejection_reason", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user_id",
            "name",
            "email",
            "role",
            "approval_status",
            "designation",
            "department",
            "mobile",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "remarks",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_name(self, obj):
        return user_display_name(obj.user)

    def get_approved_by_name(self, obj):
        if not obj.approved_by_id:
            return ""
        return user_display_name(obj.approved_by)


class AccountApprovalActionSerializer(serializers.Serializer):
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=1000,
    )

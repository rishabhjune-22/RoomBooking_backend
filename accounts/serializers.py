from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


User = get_user_model()


def normalize_email(value):
    return User.objects.normalize_email((value or "").strip()).lower()


def user_display_name(user):
    name = user.get_full_name().strip()
    return name or user.email


class AuthUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email"]

    def get_name(self, obj):
        return user_display_name(obj)


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name is required.")
        return name

    def validate_email(self, value):
        email = normalize_email(value)
        if not email:
            raise serializers.ValidationError("Email is required.")

        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(
                username__iexact=email
        ).exists():
            raise serializers.ValidationError("An account with this email already exists.")

        return email

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
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
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["name"],
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error_messages = {
        "invalid_credentials": _("Invalid email or password."),
    }

    def validate(self, attrs):
        email = normalize_email(attrs.get("email"))
        password = attrs.get("password")

        if not email or not password:
            self.fail("invalid_credentials")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            self.fail("invalid_credentials")

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        if authenticated_user is None:
            self.fail("invalid_credentials")

        if not authenticated_user.is_active:
            raise serializers.ValidationError("This account is disabled.")

        attrs["user"] = authenticated_user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    email = serializers.EmailField(required=True)

    encrypted_dek = serializers.CharField(write_only=True, required=True)
    dek_wrap_nonce = serializers.CharField(write_only=True, required=True)
    kdf_metadata = serializers.JSONField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "encrypted_dek",
            "dek_wrap_nonce",
            "kdf_metadata",
        ]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_encrypted_dek(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Encrypted DEK is required.")
        return value

    def validate_dek_wrap_nonce(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("DEK wrap nonce is required.")
        return value

    def validate_kdf_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("KDF metadata must be a JSON object.")

        required_keys = ["salt", "iterations", "key_length_bits"]
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"{key} is required in kdf_metadata.")

        if not isinstance(value["salt"], str) or not value["salt"].strip():
           raise serializers.ValidationError("salt must be a non-empty string.")

        if not isinstance(value["iterations"], int) or value["iterations"] <= 0:
            raise serializers.ValidationError("iterations must be a positive integer.")

        if not isinstance(value["key_length_bits"], int) or value["key_length_bits"] not in [128, 192, 256]:
            raise serializers.ValidationError("key_length_bits must be one of 128, 192, or 256.")

        return value

    def create(self, validated_data):
        encrypted_dek = validated_data.pop("encrypted_dek")
        dek_wrap_nonce = validated_data.pop("dek_wrap_nonce")
        kdf_metadata = validated_data.pop("kdf_metadata")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        user.encrypted_dek = encrypted_dek
        user.dek_wrap_nonce = dek_wrap_nonce
        user.kdf_metadata = kdf_metadata
        user.save(update_fields=["encrypted_dek", "dek_wrap_nonce", "kdf_metadata"])

        return user
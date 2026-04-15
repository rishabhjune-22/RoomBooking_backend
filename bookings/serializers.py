from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    room_name = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    can_view_sensitive_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "room",
            "room_name",
            "arrival_at",
            "departure_at",
            "encrypted_payload",
            "payload_nonce",
            "payload_version",
            "requestee_name",
            "requestee_designation",
            "requestee_department",
            "requestee_mobile",
            "logistics_name",
            "logistics_designation",
            "logistics_mobile",
            "status",
            "created_by_username",
            "created_at",
            "can_view_sensitive_details",
        ]
        read_only_fields = [
            "id",
            "status",
            "room_name",
            "created_by_username",
            "created_at",
            "can_view_sensitive_details",
        ]

    def get_room_name(self, obj):
        return str(obj.room)

    def get_can_view_sensitive_details(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.created_by_id == user.id)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")
        user = getattr(request, "user", None)

        is_owner = bool(
            user
            and user.is_authenticated
            and instance.created_by_id == user.id
        )

        if not is_owner:
            data["encrypted_payload"] = None
            data["payload_nonce"] = None
            data["payload_version"] = None

        return data

    def validate_encrypted_payload(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Encrypted payload is required.")
        return value

    def validate_payload_nonce(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Payload nonce is required.")
        return value

    def validate_payload_version(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Payload version must be a positive integer.")
        return value

    def validate(self, attrs):
        instance = self.instance

        room = attrs.get("room", getattr(instance, "room", None))
        arrival_at = attrs.get("arrival_at", getattr(instance, "arrival_at", None))
        departure_at = attrs.get("departure_at", getattr(instance, "departure_at", None))

        if not all([room, arrival_at, departure_at]):
            raise serializers.ValidationError(
                "Missing required booking datetime or room information."
            )

        if departure_at <= arrival_at:
            raise serializers.ValidationError(
                {"departure_at": ["Departure datetime must be after arrival datetime."]}
            )

        conflicting_bookings = Booking.objects.filter(
            room=room,
            status=Booking.STATUS_ACTIVE,
            arrival_at__lt=departure_at,
            departure_at__gt=arrival_at,
        )

        if instance:
            conflicting_bookings = conflicting_bookings.exclude(pk=instance.pk)

        conflict = conflicting_bookings.only("id", "arrival_at", "departure_at").first()

        if conflict:
            raise serializers.ValidationError(
                {
                    "room": [
                        f"{room} is already booked from "
                        f"{conflict.arrival_at} to {conflict.departure_at}."
                    ]
                }
            )

        return attrs


class BookingCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
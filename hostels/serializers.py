from rest_framework import serializers
from .models import Room


class RoomSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Room
        fields = ["id", "prefix", "number", "room_name"]
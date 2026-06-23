from rest_framework.generics import ListAPIView
from rest_framework.filters import SearchFilter
from accounts.permissions import IsAdminRole
from .models import Room
from .serializers import RoomSerializer


class RoomListView(ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [SearchFilter]
    search_fields = ["prefix", "number"]

    def get_queryset(self):
        return Room.objects.only(
            "id",
            "prefix",
            "number",
            "hostel_name",
            "has_attached_bath",
            "room_type",
            "display_order",
        ).order_by("prefix", "number")

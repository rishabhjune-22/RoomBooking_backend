from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from .models import Room
from .serializers import RoomSerializer
from rest_framework.filters import SearchFilter


class RoomListView(ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["prefix", "number"]
    def get_queryset(self):
        return Room.objects.only("id", "prefix", "number").order_by("prefix", "number")
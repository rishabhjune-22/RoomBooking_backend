from django.urls import path
from .views import RoomListView

urlpatterns = [
    path('rooms/', RoomListView.as_view(), name='room-list'),
]
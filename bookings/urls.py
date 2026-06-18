from django.urls import path

from .views import (
    BookingCreateView,
    BookingDeleteView,
    BookingDetailView,
    BookingListView,
    BookingUpdateView,
    RoomAvailabilityCalendarView,
    RoomAvailabilityDetailsView,
    AvailableRoomsByDateView,
    AvailableRoomsByDateRangeView,
)

urlpatterns = [
    path("bookings/availability/", RoomAvailabilityCalendarView.as_view(), name="room-availability"),
    path("bookings/availability/details/", RoomAvailabilityDetailsView.as_view(), name="room-availability-details"),

    path("bookings/create/", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/", BookingListView.as_view(), name="booking-list"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("bookings/<int:pk>/edit/", BookingUpdateView.as_view(), name="booking-edit"),
    path("bookings/<int:pk>/delete/", BookingDeleteView.as_view(), name="booking-delete"),
    path(
    "room-available-rooms/",
    AvailableRoomsByDateView.as_view(),
    name="room-available-rooms"
),

path(
    "room-available-rooms-range/",
    AvailableRoomsByDateRangeView.as_view(),
    name="room-available-rooms-range"
),

]

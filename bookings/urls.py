from django.urls import path

from .views import (
    AdminBookingRequestApproveView,
    AdminBookingRequestDeleteView,
    AdminBookingRequestDetailView,
    AdminBookingRequestListView,
    AdminBookingRequestRejectView,
    AdminBookingRequestSendBackView,
    BookingCreateView,
    BookingChargeSheetDetailView,
    BookingChargeSheetListView,
    BookingDeleteView,
    BookingDetailView,
    BookingListView,
    BookingShareCreateView,
    BookingUpdateView,
    RequesterAvailabilityCalendarView,
    RequesterAvailableRoomsByDateRangeView,
    RequesterBookingRequestDeleteView,
    RequesterBookingRequestDetailView,
    RequesterBookingRequestListCreateView,
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
    path("bookings/share-links/", BookingShareCreateView.as_view(), name="booking-share-create"),
    path("bookings/charge-sheet/", BookingChargeSheetListView.as_view(), name="booking-charge-sheet-list"),
    path("bookings/charge-sheet/<int:pk>/", BookingChargeSheetDetailView.as_view(), name="booking-charge-sheet-detail"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("bookings/<int:pk>/edit/", BookingUpdateView.as_view(), name="booking-edit"),
    path("bookings/<int:pk>/delete/", BookingDeleteView.as_view(), name="booking-delete"),
    path(
        "admin/booking-requests/",
        AdminBookingRequestListView.as_view(),
        name="admin-booking-request-list",
    ),
    path(
        "admin/booking-requests/<int:pk>/",
        AdminBookingRequestDetailView.as_view(),
        name="admin-booking-request-detail",
    ),
    path(
        "admin/booking-requests/<int:pk>/approve/",
        AdminBookingRequestApproveView.as_view(),
        name="admin-booking-request-approve",
    ),
    path(
        "admin/booking-requests/<int:pk>/reject/",
        AdminBookingRequestRejectView.as_view(),
        name="admin-booking-request-reject",
    ),
    path(
        "admin/booking-requests/<int:pk>/send-back/",
        AdminBookingRequestSendBackView.as_view(),
        name="admin-booking-request-send-back",
    ),
    path(
        "admin/booking-requests/<int:pk>/delete/",
        AdminBookingRequestDeleteView.as_view(),
        name="admin-booking-request-delete",
    ),
    path(
        "requester/availability/",
        RequesterAvailabilityCalendarView.as_view(),
        name="requester-availability",
    ),
    path(
        "requester/available-rooms-range/",
        RequesterAvailableRoomsByDateRangeView.as_view(),
        name="requester-available-rooms-range",
    ),
    path(
        "requester/booking-requests/",
        RequesterBookingRequestListCreateView.as_view(),
        name="requester-booking-request-list",
    ),
    path(
        "requester/booking-requests/<int:pk>/",
        RequesterBookingRequestDetailView.as_view(),
        name="requester-booking-request-detail",
    ),
    path(
        "requester/booking-requests/<int:pk>/delete/",
        RequesterBookingRequestDeleteView.as_view(),
        name="requester-booking-request-delete",
    ),
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

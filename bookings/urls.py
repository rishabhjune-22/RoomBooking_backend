from django.urls import path
from .views import BookingCreateView, BookingListView, BookingUpdateView, BookingCancelView

urlpatterns = [
    path("bookings/create/", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/", BookingListView.as_view(), name="booking-list"),
    path("bookings/<int:pk>/edit/", BookingUpdateView.as_view(), name="booking-edit"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
]
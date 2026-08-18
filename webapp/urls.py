from django.urls import path

from .views import RoomBookingWebAppView, SharedBookingSheetView, SharedChargeSheetView


app_name = "webapp"

urlpatterns = [
    path("", RoomBookingWebAppView.as_view(), name="index"),
    path("share/bookings/<slug:token>/", SharedBookingSheetView.as_view(), name="shared-bookings"),
    path("share/charges/<slug:token>/", SharedChargeSheetView.as_view(), name="shared-charges"),
]

from django.urls import path

from .views import RoomBookingWebAppView


app_name = "webapp"

urlpatterns = [
    path("", RoomBookingWebAppView.as_view(), name="index"),
]


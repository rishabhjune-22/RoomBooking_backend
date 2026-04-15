from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, CancelledBooking
from .serializers import BookingSerializer, BookingCancelSerializer


class BookingCreateView(CreateAPIView):
    queryset = Booking.objects.select_related("room", "created_by").all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save(created_by=request.user)

        return Response(
            {
                "success": True,
                "message": "Booking created successfully",
                "data": {
                    "booking_id": booking.id,
                    "room_id": booking.room.id,
                    "room_name": str(booking.room),
                    "status": booking.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class BookingListView(ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .select_related("room", "created_by")
            .all()
            .order_by("-created_at")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class BookingUpdateView(UpdateAPIView):
    queryset = Booking.objects.select_related("room", "created_by").all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        booking = super().get_object()
        if booking.created_by_id != self.request.user.id:
            raise PermissionDenied("You can edit only your own booking.")
        return booking

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Booking updated successfully",
                "data": {
                    "booking_id": booking.id,
                    "room_id": booking.room.id,
                    "room_name": str(booking.room),
                    "status": booking.status,
                },
            },
            status=status.HTTP_200_OK,
        )


class BookingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        booking = get_object_or_404(
            Booking.objects.select_related("room", "created_by"),
            pk=pk,
        )

        if booking.created_by_id != request.user.id:
            raise PermissionDenied("You can cancel only your own booking.")

        if booking.status == Booking.STATUS_CANCELLED:
            raise ValidationError({"status": ["Booking is already cancelled."]})

        serializer = BookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        CancelledBooking.objects.create(
            original_booking=booking,
            cancelled_by=request.user,
            cancellation_reason=serializer.validated_data.get("cancellation_reason", ""),
            room_name=str(booking.room),
            arrival_at=booking.arrival_at,
            departure_at=booking.departure_at,
            encrypted_payload=booking.encrypted_payload,
            payload_nonce=booking.payload_nonce,
            payload_version=booking.payload_version,
            requestee_name=booking.requestee_name,
            requestee_designation=booking.requestee_designation,
            requestee_department=booking.requestee_department,
            requestee_mobile=booking.requestee_mobile,
            logistics_name=booking.logistics_name,
            logistics_designation=booking.logistics_designation,
            logistics_mobile=booking.logistics_mobile,
        )

        booking.status = Booking.STATUS_CANCELLED
        booking.save(update_fields=["status"])

        return Response(
            {
                "success": True,
                "message": "Booking cancelled successfully",
                "data": {
                    "booking_id": booking.id,
                    "status": booking.status,
                },
            },
            status=status.HTTP_200_OK,
        )
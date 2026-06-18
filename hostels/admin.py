from django.contrib import admin
from .models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'prefix', 'number', 'room_type', 'hostel_name', 'has_attached_bath'
    ]
    list_filter = ['prefix', 'room_type', 'hostel_name', 'has_attached_bath']
    search_fields = ['prefix', 'number', 'hostel_name']

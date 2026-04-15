from django.contrib import admin
from .models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'prefix', 'number']
    search_fields = ['prefix', 'number']
from django.contrib import admin
from .models import (
    RoomFeature, Hotel, RoomType, Room, Bed,
    HospitalityPreference, Stay, RoomAssignment, BedAssignment,
)


class RoomTypeInline(admin.TabularInline):
    model = RoomType
    extra = 1


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


class BedInline(admin.TabularInline):
    model = Bed
    extra = 1


class BedAssignmentInline(admin.TabularInline):
    model = BedAssignment
    extra = 0


@admin.register(RoomFeature)
class RoomFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'city', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'event')
    search_fields = ('name', 'city', 'address')
    readonly_fields = ('created_at',)
    inlines = [RoomTypeInline]


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'hotel', 'capacity', 'base_price')
    list_filter = ('hotel',)
    search_fields = ('name', 'hotel__name')
    filter_horizontal = ('features',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'hotel', 'room_type', 'floor', 'is_available')
    list_filter = ('is_available', 'hotel', 'floor')
    search_fields = ('room_number', 'hotel__name')
    inlines = [BedInline]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'room', 'bed_type', 'label')
    list_filter = ('bed_type', 'room__hotel')
    search_fields = ('label', 'room__room_number', 'room__hotel__name')


@admin.register(HospitalityPreference)
class HospitalityPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'preferred_hotel', 'preferred_room_type', 'created_at', 'updated_at')
    list_filter = ('event', 'preferred_hotel')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('preferred_features', 'roommate_preferences')


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'hotel', 'status', 'check_in_date', 'check_out_date', 'nights')
    list_filter = ('status', 'hotel', 'event')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'hotel__name')
    readonly_fields = ('created_at', 'updated_at', 'nights')
    inlines = [BedAssignmentInline]

    # show room assignment info as readonly
    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if obj and hasattr(obj, 'room_assignment'):
            base += ['room_assignment']
        return base


@admin.register(RoomAssignment)
class RoomAssignmentAdmin(admin.ModelAdmin):
    list_display = ('stay', 'room', 'assigned_by', 'assigned_at')
    list_filter = ('room__hotel',)
    search_fields = ('stay__user__email', 'room__room_number', 'room__hotel__name')
    readonly_fields = ('assigned_at',)


@admin.register(BedAssignment)
class BedAssignmentAdmin(admin.ModelAdmin):
    list_display = ('stay', 'bed', 'assigned_by', 'assigned_at')
    list_filter = ('bed__room__hotel',)
    search_fields = ('stay__user__email', 'bed__label', 'bed__room__room_number')
    readonly_fields = ('assigned_at',)

from django.contrib import admin

from .models import (
    Event,
    EventCategory,
    EventJudgingCriteria,
    EventParticipant,
    EventResult,
    EventScore,
    EventStaffAssignment,
    EventStaffRole,
    EventTeamRegistration,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class EventCategoryInline(admin.TabularInline):
    model = EventCategory
    extra = 1
    fields = ['name', 'team_category', 'max_teams', 'order', 'description']


class EventStaffAssignmentInline(admin.TabularInline):
    model = EventStaffAssignment
    extra = 1
    fields = ['user', 'role', 'notes', 'assigned_by', 'assigned_at']
    readonly_fields = ['assigned_at']


class EventScoreInline(admin.TabularInline):
    model = EventScore
    extra = 0
    fields = ['criteria', 'judge', 'score', 'round', 'notes', 'scored_at']
    readonly_fields = ['scored_at']
    # scores are created by judges — read-only in registration context
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class EventResultInline(admin.TabularInline):
    model = EventResult
    extra = 0
    fields = ['category', 'placement', 'total_score', 'round', 'published', 'published_at', 'notes']
    readonly_fields = ['published_at']

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'status', 'start_date', 'end_date', 'venue_city', 'organizer']
    list_filter = ['status', 'event_type', 'start_date', 'end_date']
    search_fields = ['name', 'venue_name', 'venue_city', 'organizer__email', 'organizer__username']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    inlines = [EventCategoryInline, EventStaffAssignmentInline]

    fieldsets = [
        ('Basic Info', {
            'fields': ['name', 'description', 'event_type', 'status', 'organizer', 'banner'],
        }),
        ('Venue', {
            'fields': ['venue_name', 'venue_address', 'venue_city'],
        }),
        ('Dates', {
            'fields': ['start_date', 'end_date', 'registration_open', 'registration_close'],
        }),
        ('Capacity', {
            'fields': ['max_teams'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]


# ---------------------------------------------------------------------------
# EventCategory
# ---------------------------------------------------------------------------

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'team_category', 'max_teams', 'order']
    list_filter = ['event', 'team_category']
    search_fields = ['name', 'event__name', 'team_category__name']


# ---------------------------------------------------------------------------
# EventTeamRegistration
# ---------------------------------------------------------------------------

@admin.register(EventTeamRegistration)
class EventTeamRegistrationAdmin(admin.ModelAdmin):
    list_display = ['team', 'event', 'category', 'status', 'registered_at', 'registered_by']
    list_filter = ['status', 'registered_at', 'event']
    search_fields = ['team__name', 'event__name', 'registered_by__email', 'registered_by__username']
    readonly_fields = ['registered_at']
    inlines = [EventScoreInline, EventResultInline]


# ---------------------------------------------------------------------------
# EventParticipant
# ---------------------------------------------------------------------------

@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'role', 'status', 'registered_at', 'team_registration']
    list_filter = ['role', 'status', 'registered_at', 'event']
    search_fields = ['user__email', 'user__username', 'event__name']
    readonly_fields = ['registered_at']


# ---------------------------------------------------------------------------
# EventStaffRole
# ---------------------------------------------------------------------------

@admin.register(EventStaffRole)
class EventStaffRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'description']
    list_filter = ['is_active']
    search_fields = ['name', 'description']


# ---------------------------------------------------------------------------
# EventStaffAssignment
# ---------------------------------------------------------------------------

@admin.register(EventStaffAssignment)
class EventStaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'event', 'assigned_by', 'assigned_at']
    list_filter = ['role', 'assigned_at', 'event']
    search_fields = ['user__email', 'user__username', 'event__name', 'role__name']
    readonly_fields = ['assigned_at']


# ---------------------------------------------------------------------------
# EventJudgingCriteria
# ---------------------------------------------------------------------------

@admin.register(EventJudgingCriteria)
class EventJudgingCriteriaAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'weight', 'max_score', 'order', 'is_active']
    list_filter = ['is_active', 'event']
    search_fields = ['name', 'event__name']


# ---------------------------------------------------------------------------
# EventScore
# ---------------------------------------------------------------------------

@admin.register(EventScore)
class EventScoreAdmin(admin.ModelAdmin):
    list_display = ['judge', 'team_registration', 'criteria', 'score', 'round', 'scored_at']
    list_filter = ['round', 'scored_at', 'criteria__event']
    search_fields = ['judge__email', 'judge__username', 'team_registration__team__name']
    readonly_fields = ['scored_at']


# ---------------------------------------------------------------------------
# EventResult
# ---------------------------------------------------------------------------

@admin.register(EventResult)
class EventResultAdmin(admin.ModelAdmin):
    list_display = ['placement', 'team_registration', 'category', 'total_score', 'round', 'published', 'published_at']
    list_filter = ['round', 'published', 'category__event']
    search_fields = ['team_registration__team__name', 'category__name', 'category__event__name']
    readonly_fields = ['published_at']

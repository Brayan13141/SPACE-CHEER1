# orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_type",
        "status",
        "owner_user",
        "owner_team",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "order_type")
    search_fields = ("owner_user__email", "owner_team__name", "created_by__email")
    raw_id_fields = ("owner_user", "owner_team", "created_by")
    readonly_fields = ("created_at", "updated_at")

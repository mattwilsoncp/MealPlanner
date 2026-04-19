from django.contrib import admin
from .models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "quantity",
        "unit",
        "category",
        "location",
        "expiration_date",
    ]
    list_filter = ["category", "location"]
    search_fields = ["name"]
    ordering = ["name"]

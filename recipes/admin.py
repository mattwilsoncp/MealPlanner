from django.contrib import admin
from .models import Recipe


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "household", "needs_review", "created_at"]
    list_filter = ["needs_review", "on_hand_idea", "leftover_worthy", "created_at"]
    search_fields = ["title", "description"]
    raw_id_fields = ["household"]

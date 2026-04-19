from django.contrib import admin
from ratings.models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["recipe", "user", "score", "created_at"]
    list_filter = ["score", "user"]
    search_fields = ["recipe__title"]

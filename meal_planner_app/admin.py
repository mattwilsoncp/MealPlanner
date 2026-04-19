from django.contrib import admin
from .models import MealPlan


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "household",
        "meal_date",
        "meal_type",
        "recipe",
        "custom_meal",
    ]
    list_filter = ["meal_date", "meal_type"]
    search_fields = ["recipe__title", "custom_meal"]
    raw_id_fields = ["household", "recipe"]

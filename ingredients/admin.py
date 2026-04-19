from django.contrib import admin
from ingredients.models import Ingredient, IngredientLink


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "household", "usda_food_id", "created_at"]
    list_filter = ["household"]
    search_fields = ["name"]


@admin.register(IngredientLink)
class IngredientLinkAdmin(admin.ModelAdmin):
    list_display = ["recipe", "ingredient", "quantity", "unit", "order"]
    list_filter = ["recipe", "unit"]
    search_fields = ["recipe__title", "ingredient__name"]

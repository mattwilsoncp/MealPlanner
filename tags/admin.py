from django.contrib import admin
from tags.models import Tag, RecipeTag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "household", "color"]
    list_filter = ["household"]
    search_fields = ["name"]


@admin.register(RecipeTag)
class RecipeTagAdmin(admin.ModelAdmin):
    list_display = ["recipe", "tag"]
    list_filter = ["recipe", "tag"]

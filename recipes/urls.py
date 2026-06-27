from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views
from . import api

app_name = "recipes"

urlpatterns = [
    # Template views
    path("", views.RecipeListView.as_view(), name="recipe_list"),
    path("import/", views.LLMRecipeImportView.as_view(), name="recipe_import"),
    path("import/llm/", views.LLMRecipeImportView.as_view(), name="llm_recipe_import"),
    path("import/image/", views.ImageRecipeImportView.as_view(), name="image_recipe_import"),
    path("<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("<int:pk>/transcript/", views.RecipeTranscriptContentView.as_view(), name="recipe_transcript"),
    path("new/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("<int:pk>/edit/", views.RecipeUpdateView.as_view(), name="recipe_update"),
    path("<int:pk>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    path("<int:pk>/rate/", views.recipe_rate_view, name="recipe_rate"),
    # JSON API endpoints
    path("api/list/", api.recipe_list_api, name="recipe_list_api"),
    path(
        "api/<int:pk>/toggle-review/",
        api.recipe_toggle_review,
        name="recipe_toggle_review",
    ),
    path("api/search/", api.recipe_search_api, name="recipe_search_api"),
    path("api/<int:pk>/", api.recipe_detail_api, name="recipe_detail_api"),
]

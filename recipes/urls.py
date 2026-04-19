from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.RecipeListView.as_view(), name="recipe_list"),
    path("<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("new/", views.RecipeCreateView.as_view(), name="recipe_create"),
    path("<int:pk>/edit/", views.RecipeUpdateView.as_view(), name="recipe_update"),
    path("<int:pk>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    path("<int:pk>/rate/", views.recipe_rate_view, name="recipe_rate"),
]

from django.urls import path
from . import views

app_name = "meal_planner"

urlpatterns = [
    path("planner/", views.PlannerHomeView.as_view(), name="planner"),
    path(
        "planner/<int:year>/<int:week>/",
        views.PlannerHomeView.as_view(),
        name="planner_week",
    ),
    path("planner/navigate/", views.week_navigate, name="planner_navigate"),
    path("api/meals/", views.json_week_meals, name="api_meals"),
    # Recipe API endpoints
    path(
        "api/recipes/select/",
        views.RecipeSelectView.as_view(),
        name="api_recipe_select",
    ),
    path(
        "api/recipes/expiring/",
        views.RecipeExpiringMatchView.as_view(),
        name="api_recipes_expiring",
    ),
    path(
        "api/recipes/<int:pk>/",
        views.RecipeDetailView.as_view(),
        name="api_recipe_detail",
    ),
    path(
        "api/meals/<int:meal_id>/side_dishes/",
        views.json_side_dishes,
        name="api_side_dishes",
    ),
    # Meal CRUD URLs
    path("meal/add/", views.AddMealView.as_view(), name="add_meal"),
    path("meal/<int:meal_id>/edit/", views.EditMealView.as_view(), name="edit_meal"),
    path(
        "meal/<int:meal_id>/delete/", views.DeleteMealView.as_view(), name="delete_meal"
    ),
    path("meal/<int:meal_id>/rate/", views.RateMealView.as_view(), name="rate_meal"),
    path("meal/<int:meal_id>/move/", views.MoveMealView.as_view(), name="move_meal"),
    # On-Hand Ideas URLs
    path("on-hand/", views.OnHandIdeasView.as_view(), name="on_hand_ideas"),
    path(
        "on-hand/add-to-meal/",
        views.AddOnHandToMealView.as_view(),
        name="add_on_hand_to_meal",
    ),
    # On-Hand API endpoints
    path(
        "api/recipe/<int:recipe_id>/toggle-on-hand/",
        views.ToggleOnHandIdeaView.as_view(),
        name="toggle_on_hand",
    ),
    path(
        "api/recipe/<int:recipe_id>/toggle-leftover/",
        views.ToggleLeftoverWorthyView.as_view(),
        name="toggle_leftover",
    ),
    path(
        "api/on-hand/recipes/",
        views.JsonOnHandRecipesView.as_view(),
        name="api_on_hand_recipes",
    ),
    path(
        "api/leftover/recipes/",
        views.JsonLeftoverRecipesView.as_view(),
        name="api_leftover_recipes",
    ),
    # Cooking URLs
    path("cooking/", views.CookingHomeView.as_view(), name="cooking_home"),
    path(
        "cooking/<int:meal_id>/",
        views.CookingReconciliationView.as_view(),
        name="cooking_reconcile",
    ),
    path(
        "api/cooking/<int:meal_id>/data/",
        views.json_reconciliation_data,
        name="api_cooking_data",
    ),
    path(
        "api/cooking/<int:meal_id>/process/",
        views.ProcessCookingView.as_view(),
        name="process_cooking",
    ),
    path(
        "api/cooking/<int:meal_id>/toggle/",
        views.MarkIngredientUsedView.as_view(),
        name="toggle_ingredient_used",
    ),
]

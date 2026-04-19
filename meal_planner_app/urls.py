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
    # Meal CRUD URLs
    path("meal/add/", views.AddMealView.as_view(), name="add_meal"),
    path("meal/<int:meal_id>/edit/", views.EditMealView.as_view(), name="edit_meal"),
    path(
        "meal/<int:meal_id>/delete/", views.DeleteMealView.as_view(), name="delete_meal"
    ),
    path("meal/<int:meal_id>/rate/", views.RateMealView.as_view(), name="rate_meal"),
]

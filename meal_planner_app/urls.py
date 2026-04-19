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
]

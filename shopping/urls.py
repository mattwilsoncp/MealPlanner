from django.urls import path

from .views import RegenerateShoppingWeekView, ShoppingWeekView

app_name = "shopping"

urlpatterns = [
    path("", ShoppingWeekView.as_view(), name="week"),
    path("regenerate/", RegenerateShoppingWeekView.as_view(), name="regenerate_week"),
]

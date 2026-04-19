from django.urls import path

from .views import (
    ClearShoppingWeekView,
    DeleteShoppingItemView,
    RegenerateShoppingWeekView,
    ShoppingWeekView,
    ToggleShoppingItemView,
)

app_name = "shopping"

urlpatterns = [
    path("", ShoppingWeekView.as_view(), name="week"),
    path("regenerate/", RegenerateShoppingWeekView.as_view(), name="regenerate_week"),
    path(
        "api/item/<int:item_id>/toggle/",
        ToggleShoppingItemView.as_view(),
        name="item_toggle",
    ),
    path(
        "api/item/<int:item_id>/delete/",
        DeleteShoppingItemView.as_view(),
        name="item_delete",
    ),
    path("api/week/clear/", ClearShoppingWeekView.as_view(), name="week_clear"),
]

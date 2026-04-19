from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryListView.as_view(), name="inventory_list"),
    path("create/", views.InventoryCreateAPIView.as_view(), name="inventory_create"),
    path(
        "create/api/",
        views.InventoryCreateAPIView.as_view(),
        name="inventory_create_api",
    ),
]

from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryListView.as_view(), name="inventory_list"),
    path("add/", views.InventoryCreateView.as_view(), name="inventory_add"),
    path(
        "<int:item_id>/edit/",
        views.InventoryUpdateView.as_view(),
        name="inventory_edit",
    ),
    path(
        "<int:item_id>/delete/",
        views.InventoryDeleteView.as_view(),
        name="inventory_delete",
    ),
    path("expiring/", views.InventoryExpiringView.as_view(), name="inventory_expiring"),
    path("expired/", views.InventoryExpiredView.as_view(), name="inventory_expired"),
    path(
        "api/quick-add/",
        views.InventoryQuickAddView.as_view(),
        name="inventory_quick_add",
    ),
    path(
        "api/barcode/lookup/",
        views.BarcodeLookupView.as_view(),
        name="barcode_lookup_api",
    ),
    path(
        "create/api/",
        views.InventoryQuickAddView.as_view(),
        name="inventory_create_api",
    ),
]

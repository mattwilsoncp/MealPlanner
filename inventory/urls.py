from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryListView.as_view(), name="inventory_list"),
    path("barcode/", views.BarcodeScanPageView.as_view(), name="barcode_scan"),
    path("receipt/import/", views.ReceiptImportView.as_view(), name="receipt_import"),
    path("receipt/review/", views.ReceiptImportReviewView.as_view(), name="receipt_import_review"),
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
        "stores/",
        views.StoreListView.as_view(),
        name="store_list",
    ),
    path(
        "stores/add/",
        views.StoreCreateView.as_view(),
        name="store_add",
    ),
    path(
        "stores/<int:pk>/edit/",
        views.StoreUpdateView.as_view(),
        name="store_edit",
    ),
    path(
        "stores/<int:pk>/delete/",
        views.StoreDeleteView.as_view(),
        name="store_delete",
    ),
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
        "api/barcode/create/",
        views.BarcodeCreateView.as_view(),
        name="barcode_create_api",
    ),
    path(
        "create/api/",
        views.InventoryQuickAddView.as_view(),
        name="inventory_create_api",
    ),
]

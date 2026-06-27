from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

from .backup import BackupPageView, ExportBackupView, ImportBackupView
from .views import HomePageView
from inventory.views import UpcUsageView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("recipes/", include("recipes.urls", namespace="recipes")),
    path("reviews/", include("reviews.urls", namespace="reviews")),
    path("inventory/", include("inventory.urls", namespace="inventory")),
    path("ingredients/", include("ingredients.urls", namespace="ingredients")),
    path("", include("meal_planner_app.urls", namespace="meal_planner")),
    path("shopping/", include("shopping.urls", namespace="shopping")),
    path("tags/", include("tags.urls", namespace="tags")),
    path("ratings/", include("ratings.urls", namespace="ratings")),
    path("", HomePageView.as_view(), name="home"),
    path(
        "accounts/logged-out/",
        TemplateView.as_view(template_name="registration/logged_out.html"),
        name="logged_out",
    ),
    # Backup & Restore
    path("tools/backup/", BackupPageView.as_view(), name="backup_page"),
    path("tools/backup/export/", ExportBackupView.as_view(), name="backup_export"),
    path("tools/backup/import/", ImportBackupView.as_view(), name="backup_import"),
    # UPC lookup usage monitor
    path("tools/upc-usage/", UpcUsageView.as_view(), name="upc_usage"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

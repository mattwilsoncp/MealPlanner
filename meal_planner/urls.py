from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("recipes/", include("recipes.urls", namespace="recipes")),
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path(
        "accounts/logged-out/",
        TemplateView.as_view(template_name="registration/logged_out.html"),
        name="logged_out",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path
from . import api

app_name = "ratings"

urlpatterns = [
    path("api/recipe/<int:recipe_pk>/rating/", api.rating_get_api, name="rating_get"),
    path("api/recipe/<int:recipe_pk>/rate/", api.rating_create_api, name="rating_create"),
]
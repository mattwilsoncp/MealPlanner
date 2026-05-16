from django.urls import path
from . import api

app_name = "ingredients"

urlpatterns = [
    path("api/list/", api.ingredient_list_api, name="ingredient_list_api"),
    path("api/search/", api.ingredient_search_api, name="ingredient_search_api"),
]
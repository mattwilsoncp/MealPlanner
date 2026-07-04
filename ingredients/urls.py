from django.urls import path
from . import api, views

app_name = "ingredients"

urlpatterns = [
    path("<int:pk>/link-usda/", views.ingredient_usda_link_view, name="link_usda"),
    path("api/list/", api.ingredient_list_api, name="ingredient_list_api"),
    path("api/search/", api.ingredient_search_api, name="ingredient_search_api"),
]

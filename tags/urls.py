from django.urls import path

from . import api

app_name = "tags"

urlpatterns = [
    path("api/tags/", api.tag_list_api, name="tag_list_api"),
    path("api/tags/create/", api.tag_create_api, name="tag_create_api"),
]
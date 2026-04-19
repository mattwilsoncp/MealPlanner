from django.urls import path
from . import views

app_name = "reviews"

urlpatterns = [
    path("queue/", views.ReviewQueueView.as_view(), name="review_queue"),
    path("", views.ReviewQueueView.as_view(), name="review_queue_legacy"),
    path("<int:pk>/ready/", views.MarkReadyView.as_view(), name="mark_ready"),
    path(
        "<int:pk>/reconcile/",
        views.RecipeReconcileView.as_view(),
        name="recipe_reconcile",
    ),
    path(
        "<int:pk>/reconcile/save/",
        views.SaveReconciliationView.as_view(),
        name="save_reconciliation",
    ),
]

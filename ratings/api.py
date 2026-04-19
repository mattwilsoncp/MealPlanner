"""JSON API endpoints for ratings."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from ratings.models import Rating
from recipes.models import Recipe
import json


@login_required
@require_http_methods(["GET"])
def rating_get_api(request, recipe_pk):
    """Get rating for a specific recipe."""
    recipe = get_object_or_404(Recipe, pk=recipe_pk, household=request.user.household)

    rating = Rating.objects.filter(recipe=recipe, user=request.user).first()

    if rating:
        return JsonResponse(
            {
                "id": rating.id,
                "score": rating.score,
                "notes": rating.notes,
            }
        )
    else:
        return JsonResponse({"rating": None})


@login_required
@require_POST
@csrf_exempt
def rating_create_api(request, recipe_pk):
    """Create or update rating for a recipe (upsert)."""
    recipe = get_object_or_404(Recipe, pk=recipe_pk, household=request.user.household)

    try:
        data = json.loads(request.body)
        score = data.get("score")
        notes = data.get("notes", "")

        if score is None or not (1 <= score <= 5):
            return JsonResponse({"error": "Score must be between 1 and 5"}, status=400)

        # Check if rating already exists (upsert)
        rating = Rating.objects.filter(recipe=recipe, user=request.user).first()
        if rating:
            rating.score = score
            rating.notes = notes
            rating.save()
        else:
            rating = Rating.objects.create(
                recipe=recipe,
                user=request.user,
                score=score,
                notes=notes,
            )

        return JsonResponse(
            {
                "id": rating.id,
                "score": rating.score,
                "notes": rating.notes,
                "updated": rating.pk is not None,
            }
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

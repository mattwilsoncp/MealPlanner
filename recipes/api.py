"""JSON API endpoints for recipes."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from recipes.models import Recipe
from tags.models import RecipeTag


@login_required
@require_http_methods(["GET"])
def recipe_list_api(request):
    """Return JSON list of recipes for the household."""
    recipes = (
        Recipe.objects.filter(household=request.user.household, needs_review=False)
        .select_related("household")
        .prefetch_related("tags", "tag_set")
    )

    data = []
    for recipe in recipes:
        # Get average rating
        ratings = recipe.rating_set.all()
        avg_rating = None
        if ratings.exists():
            avg_rating = (
                sum(r.values_list("score", flat=True) for r in [ratings])
                / ratings.count()
            )

        # Get tags
        tag_list = list(
            RecipeTag.objects.filter(recipe=recipe)
            .select_related("tag")
            .values_list("tag__name", flat=True)
        )

        data.append(
            {
                "id": recipe.id,
                "title": recipe.title,
                "description": recipe.description,
                "photo_url": recipe.photo.url if recipe.photo else None,
                "rating": avg_rating,
                "tags": tag_list,
                "needs_review": recipe.needs_review,
                "on_hand_idea": recipe.on_hand_idea,
                "leftover_worthy": recipe.leftover_worthy,
                "created_at": recipe.created_at.isoformat()
                if recipe.created_at
                else None,
            }
        )

    return JsonResponse({"recipes": data})


@login_required
@require_http_methods(["POST"])
def recipe_toggle_review(request, pk):
    """Toggle needs_review boolean for a recipe."""
    try:
        recipe = Recipe.objects.get(pk=pk, household=request.user.household)
    except Recipe.DoesNotExist:
        return JsonResponse({"error": "Recipe not found"}, status=404)

    recipe.needs_review = not recipe.needs_review
    recipe.save()

    return JsonResponse(
        {
            "success": True,
            "needs_review": recipe.needs_review,
            "recipe_id": recipe.id,
        }
    )


@login_required
@require_http_methods(["GET"])
def recipe_search_api(request):
    """Search recipes by query parameter q."""
    q = request.GET.get("q", "").strip()

    if not q:
        return JsonResponse({"recipes": []})

    recipes = (
        Recipe.objects.filter(household=request.user.household)
        .filter(
            # Using Q for OR search
        )
        .distinct()[:20]
    )  # Limit results

    from django.db.models import Q

    recipes = Recipe.objects.filter(household=request.user.household).filter(
        Q(title__icontains=q) | Q(description__icontains=q)
    )[:20]

    data = []
    for recipe in recipes:
        data.append(
            {
                "id": recipe.id,
                "title": recipe.title,
                "description": recipe.description[:100] if recipe.description else "",
                "photo_url": recipe.photo.url if recipe.photo else None,
            }
        )

    return JsonResponse({"recipes": data})

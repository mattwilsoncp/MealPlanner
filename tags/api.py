"""JSON API endpoints for tags."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from tags.models import Tag


@login_required
@require_http_methods(["GET"])
def tag_list_api(request):
    """Return JSON list of tags for the household."""
    tags = Tag.objects.filter(household=request.user.household).order_by("name")

    data = []
    for tag in tags:
        data.append(
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
            }
        )

    return JsonResponse({"tags": data})


@login_required
@require_POST
@csrf_exempt
def tag_create_api(request):
    """Create a new tag."""
    import json

    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        color = data.get("color", "#6b7280")

        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)

        # Check if tag already exists
        existing = Tag.objects.filter(
            household=request.user.household, name__iexact=name
        ).first()
        if existing:
            return JsonResponse(
                {
                    "id": existing.id,
                    "name": existing.name,
                    "color": existing.color,
                    "exists": True,
                }
            )

        tag = Tag.objects.create(
            household=request.user.household,
            name=name,
            color=color,
        )

        return JsonResponse(
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "created": True,
            }
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

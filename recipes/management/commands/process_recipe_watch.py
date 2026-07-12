"""Generate a watch view for one or more recipes.

Usage:

    # Process a single recipe by primary key
    python manage.py process_recipe_watch 42

    # Process all recipes in a household that have a video URL
    python manage.py process_recipe_watch --household-id 1

    # Limit the number of segments per video
    python manage.py process_recipe_watch 42 --max-segments 20
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from recipes.models import Recipe
from recipes.watch_service import process_recipe_watch


class Command(BaseCommand):
    help = "Download recipe videos and build frame + transcript watch views"

    def add_arguments(self, parser):
        parser.add_argument(
            "recipe_id",
            nargs="?",
            type=int,
            help="Primary key of the recipe to process",
        )
        parser.add_argument(
            "--household-id",
            type=int,
            help="Process all recipes with a video URL for this household",
        )
        parser.add_argument(
            "--max-segments",
            type=int,
            default=30,
            help="Maximum number of transcript segments per video (default: 30)",
        )

    def handle(self, *args, **options):
        recipe_id = options.get("recipe_id")
        household_id = options.get("household_id")
        max_segments = options.get("max_segments", 30)

        if recipe_id is None and household_id is None:
            raise CommandError(
                "Provide a recipe_id or --household-id"
            )

        queryset = Recipe.objects.exclude(video_url="")
        if recipe_id is not None:
            queryset = queryset.filter(pk=recipe_id)
        if household_id is not None:
            queryset = queryset.filter(household_id=household_id)

        recipes = list(queryset)
        if not recipes:
            raise CommandError(
                "No recipes with a video URL matched the given filters"
            )

        for recipe in recipes:
            self.stdout.write(
                f"Processing recipe #{recipe.pk}: {recipe.title}"
            )
            try:
                process_recipe_watch(
                    recipe,
                    max_segments=max_segments,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Watch view ready ({recipe.watch_session.segments.count()} segments)"
                    )
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  Failed: {exc}")
                )

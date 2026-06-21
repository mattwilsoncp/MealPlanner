import io
import json
import os
import zipfile
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction
from inventory.models import InventoryItem
from recipes.models import Recipe
from tags.models import RecipeTag, Tag

BACKUP_VERSION = 2


class BackupPageView(LoginRequiredMixin, TemplateView):
    template_name = "backup/backup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = self.request.user.household
        if household:
            context["recipe_count"] = Recipe.objects.filter(household=household).count()
            context["inventory_count"] = InventoryItem.objects.filter(household=household).count()
        else:
            context["recipe_count"] = 0
            context["inventory_count"] = 0
        return context


class ExportBackupView(LoginRequiredMixin, View):
    def get(self, request):
        household = request.user.household
        if not household:
            return JsonResponse(
                {"ok": False, "message": "No household assigned to your account."},
                status=400,
            )

        recipes_data, photo_files = self._export_recipes(household)
        data = {
            "version": BACKUP_VERSION,
            "exported_at": timezone.now().isoformat(),
            "household_name": household.name,
            "recipes": recipes_data,
            "inventory": self._export_inventory(household),
        }

        # Build a ZIP containing backup.json + photos/
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(data, indent=2, ensure_ascii=False))
            for photo_path, photo_bytes in photo_files:
                zf.writestr(f"photos/{photo_path}", photo_bytes)

        buffer.seek(0)
        filename = f"meal_planner_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _export_recipes(self, household):
        recipes = Recipe.objects.filter(household=household)
        result = []
        photo_files = []  # list of (filename, bytes)
        for recipe in recipes:
            ingredients = IngredientLink.objects.filter(recipe=recipe).select_related(
                "ingredient"
            )
            instructions = Instruction.objects.filter(recipe=recipe)
            recipe_tags = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

            # Export photo if present
            photo_filename = None
            if recipe.photo:
                try:
                    ext = os.path.splitext(recipe.photo.name)[1] or ".jpg"
                    photo_filename = f"recipe_{recipe.pk}{ext}"
                    recipe.photo.open("rb")
                    photo_files.append((photo_filename, recipe.photo.read()))
                    recipe.photo.close()
                except Exception:
                    photo_filename = None

            result.append(
                {
                    "title": recipe.title,
                    "description": recipe.description,
                    "video_url": recipe.video_url,
                    "on_hand_idea": recipe.on_hand_idea,
                    "leftover_worthy": recipe.leftover_worthy,
                    "needs_review": recipe.needs_review,
                    "photo_filename": photo_filename,
                    "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
                    "ingredients": [
                        {
                            "name": link.ingredient.name,
                            "quantity": str(link.quantity),
                            "unit": link.unit,
                            "order": link.order,
                        }
                        for link in ingredients
                    ],
                    "instructions": [
                        {
                            "step_number": inst.step_number,
                            "text": inst.text,
                        }
                        for inst in instructions
                    ],
                    "tags": [rt.tag.name for rt in recipe_tags],
                }
            )
        return result, photo_files

    def _export_inventory(self, household):
        items = InventoryItem.objects.filter(household=household)
        return [
            {
                "name": item.name,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "category": item.category,
                "location": item.location,
                "expiration_date": item.expiration_date.isoformat()
                if item.expiration_date
                else None,
                "notes": item.notes,
                "barcode": item.barcode,
            }
            for item in items
        ]


class ImportBackupView(LoginRequiredMixin, View):
    def post(self, request):
        uploaded = request.FILES.get("backup_file")
        if not uploaded:
            return JsonResponse(
                {"ok": False, "message": "No file uploaded."}, status=400
            )

        # Detect format: ZIP or legacy JSON
        file_bytes = uploaded.read()
        photos_archive = None

        try:
            zf = zipfile.ZipFile(io.BytesIO(file_bytes))
            json_data = zf.read("backup.json").decode("utf-8")
            data = json.loads(json_data)
            photos_archive = zf
        except (zipfile.BadZipFile, KeyError):
            # Fall back to plain JSON (v1 format)
            try:
                data = json.loads(file_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse(
                    {"ok": False, "message": "Invalid backup file. Expected ZIP or JSON."}, status=400
                )

        version = data.get("version")
        if version not in (1, 2, BACKUP_VERSION):
            return JsonResponse(
                {
                    "ok": False,
                    "message": f"Unsupported backup version: {version}",
                },
                status=400,
            )

        household = request.user.household
        stats = {"recipes_imported": 0, "inventory_imported": 0, "skipped": 0}

        # Import recipes
        for recipe_data in data.get("recipes", []):
            title = recipe_data.get("title", "").strip()
            if not title:
                stats["skipped"] += 1
                continue

            # Skip duplicates by title
            if Recipe.objects.filter(household=household, title=title).exists():
                stats["skipped"] += 1
                continue

            recipe = Recipe.objects.create(
                household=household,
                title=title,
                description=recipe_data.get("description", ""),
                video_url=recipe_data.get("video_url", ""),
                on_hand_idea=recipe_data.get("on_hand_idea", False),
                leftover_worthy=recipe_data.get("leftover_worthy", False),
                needs_review=recipe_data.get("needs_review", True),
            )

            # Restore photo from ZIP archive
            photo_filename = recipe_data.get("photo_filename")
            if photo_filename and photos_archive:
                try:
                    photo_bytes = photos_archive.read(f"photos/{photo_filename}")
                    recipe.photo.save(
                        photo_filename, ContentFile(photo_bytes), save=True
                    )
                except (KeyError, Exception):
                    pass

            # Import ingredients
            for ing_data in recipe_data.get("ingredients", []):
                ing_name = ing_data.get("name", "").strip()
                if not ing_name:
                    continue
                ingredient, _ = Ingredient.objects.get_or_create(
                    household=household,
                    name=ing_name,
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ingredient,
                    quantity=ing_data.get("quantity", "1"),
                    unit=ing_data.get("unit", "piece"),
                    order=ing_data.get("order", 0),
                )

            # Import instructions
            for inst_data in recipe_data.get("instructions", []):
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=inst_data.get("step_number", 1),
                    text=inst_data.get("text", ""),
                )

            # Import tags
            for tag_name in recipe_data.get("tags", []):
                tag_name = tag_name.strip()
                if not tag_name:
                    continue
                tag, _ = Tag.objects.get_or_create(
                    household=household,
                    name=tag_name,
                )
                RecipeTag.objects.get_or_create(recipe=recipe, tag=tag)

            stats["recipes_imported"] += 1

        # Import inventory
        for item_data in data.get("inventory", []):
            name = item_data.get("name", "").strip()
            if not name:
                stats["skipped"] += 1
                continue

            # Skip duplicates by name + barcode
            barcode = item_data.get("barcode", "")
            if barcode and InventoryItem.objects.filter(
                household=household, barcode=barcode
            ).exists():
                stats["skipped"] += 1
                continue

            exp_date = item_data.get("expiration_date")

            InventoryItem.objects.create(
                household=household,
                name=name,
                quantity=item_data.get("quantity", "1"),
                unit=item_data.get("unit", "piece"),
                category=item_data.get("category", "other"),
                location=item_data.get("location", "pantry"),
                expiration_date=exp_date if exp_date else None,
                notes=item_data.get("notes", ""),
                barcode=barcode,
            )
            stats["inventory_imported"] += 1

        if photos_archive:
            photos_archive.close()

        return JsonResponse({"ok": True, "stats": stats})

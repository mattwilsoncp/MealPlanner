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
from inventory.models import InventoryCategory, InventoryItem, Store
from meal_planner_app.models import AISettings, MealPlan, MealPreferences, SideDish
from recipes.models import Recipe, RecipeWatchSegment, RecipeWatchSession
from shopping.models import ShoppingListItem, ShoppingListWeek
from tags.models import RecipeTag, Tag

BACKUP_VERSION = 6


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

        recipes_data, recipe_media = self._export_recipes(household)
        inventory_data, inventory_media = self._export_inventory(household)
        data = {
            "version": BACKUP_VERSION,
            "exported_at": timezone.now().isoformat(),
            "household_name": household.name,
            "stores": self._export_stores(household),
            "inventory_categories": self._export_inventory_categories(),
            "ingredients": self._export_ingredients(household),
            "recipes": recipes_data,
            "inventory": inventory_data,
            "meal_preferences": self._export_meal_preferences(household),
            "ai_settings": self._export_ai_settings(household),
            "meal_plans": self._export_meal_plans(household),
            "shopping_lists": self._export_shopping_lists(household),
            "ratings": self._export_ratings(household),
        }

        media_files = []
        media_files.extend(recipe_media)
        media_files.extend(inventory_media)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(data, indent=2, ensure_ascii=False))
            for zip_path, file_bytes in media_files:
                zf.writestr(zip_path, file_bytes)

        buffer.seek(0)
        filename = f"meal_planner_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _read_image(self, fieldfile):
        if not fieldfile:
            return None
        try:
            fieldfile.open("rb")
            return fieldfile.read()
        except Exception:
            return None
        finally:
            try:
                fieldfile.close()
            except Exception:
                pass

    def _export_stores(self, household):
        return [
            {
                "name": store.name,
                "notes": store.notes,
            }
            for store in Store.objects.filter(household=household).order_by("name")
        ]

    def _export_inventory_categories(self):
        return [
            {
                "slug": category.slug,
                "name": category.name,
                "sort_order": category.sort_order,
                "is_protected": category.is_protected,
            }
            for category in InventoryCategory.objects.order_by("sort_order", "slug")
        ]

    def _export_ingredients(self, household):
        return [
            {
                "name": ingredient.name,
                "usda_food_id": ingredient.usda_food_id,
                "calories_kcal": (
                    str(ingredient.calories_kcal) if ingredient.calories_kcal is not None else None
                ),
                "protein_g": (
                    str(ingredient.protein_g) if ingredient.protein_g is not None else None
                ),
                "carbs_g": (
                    str(ingredient.carbs_g) if ingredient.carbs_g is not None else None
                ),
                "fat_g": (
                    str(ingredient.fat_g) if ingredient.fat_g is not None else None
                ),
            }
            for ingredient in Ingredient.objects.filter(household=household).order_by("name")
        ]

    def _export_recipes(self, household):
        recipes = Recipe.objects.filter(household=household)
        result = []
        media_files = []  # list of (zip_path, bytes)
        for recipe in recipes:
            ingredients = IngredientLink.objects.filter(recipe=recipe).select_related(
                "ingredient"
            )
            instructions = Instruction.objects.filter(recipe=recipe)
            recipe_tags = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

            photo_path = None
            if recipe.photo:
                ext = os.path.splitext(recipe.photo.name)[1] or ".jpg"
                photo_filename = f"recipe_{recipe.pk}{ext}"
                photo_bytes = self._read_image(recipe.photo)
                if photo_bytes:
                    photo_path = f"photos/{photo_filename}"
                    media_files.append((photo_path, photo_bytes))

            instruction_entries = []
            for index, inst in enumerate(instructions.order_by("step_number"), start=1):
                image_path = None
                if inst.image:
                    ext = os.path.splitext(inst.image.name)[1] or ".jpg"
                    image_filename = f"recipe_{recipe.pk}_instruction_{index:04d}{ext}"
                    image_bytes = self._read_image(inst.image)
                    if image_bytes:
                        image_path = f"instruction_images/{image_filename}"
                        media_files.append((image_path, image_bytes))

                instruction_entries.append(
                    {
                        "step_number": inst.step_number,
                        "text": inst.text,
                        "image_path": image_path,
                    }
                )

            watch_session_data = None
            if hasattr(recipe, "watch_session"):
                session = recipe.watch_session
                segments = []
                for index, segment in enumerate(
                    session.segments.order_by("start_time"), start=1
                ):
                    frame_path = None
                    if segment.image:
                        ext = os.path.splitext(segment.image.name)[1] or ".jpg"
                        frame_filename = f"recipe_{recipe.pk}_segment_{index:04d}{ext}"
                        frame_bytes = self._read_image(segment.image)
                        if frame_bytes:
                            frame_path = f"watch_frames/{recipe.pk}/{frame_filename}"
                            media_files.append((frame_path, frame_bytes))

                    segments.append(
                        {
                            "start_time": str(segment.start_time),
                            "end_time": str(segment.end_time),
                            "text": segment.text,
                            "step_number": segment.step_number,
                            "frame_path": frame_path,
                        }
                    )

                watch_session_data = {
                    "status": session.status,
                    "error_message": session.error_message,
                    "segments": segments,
                }

            result.append(
                {
                    "title": recipe.title,
                    "description": recipe.description,
                    "video_url": recipe.video_url,
                    "transcript_log": recipe.transcript_log,
                    "on_hand_idea": recipe.on_hand_idea,
                    "leftover_worthy": recipe.leftover_worthy,
                    "needs_review": recipe.needs_review,
                    "photo_path": photo_path,
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
                    "instructions": instruction_entries,
                    "tags": [
                        {"name": rt.tag.name, "color": rt.tag.color}
                        for rt in recipe_tags
                    ],
                    "watch_session": watch_session_data,
                }
            )
        return result, media_files

    def _export_inventory(self, household):
        store_lookup = {
            store.pk: store.name
            for store in Store.objects.filter(household=household)
        }
        items = InventoryItem.objects.filter(household=household)
        result = []
        media_files = []
        for index, item in enumerate(items, start=1):
            image_path = None
            if item.image:
                ext = os.path.splitext(item.image.name)[1] or ".jpg"
                image_filename = f"inventory_{item.pk}{ext}"
                image_bytes = self._read_image(item.image)
                if image_bytes:
                    image_path = f"inventory_images/{image_filename}"
                    media_files.append((image_path, image_bytes))

            result.append(
                {
                    "name": item.name,
                    "quantity": str(item.quantity),
                    "unit": item.unit,
                    "category": item.category,
                    "location": item.location,
                    "expiration_date": item.expiration_date.isoformat()
                    if item.expiration_date
                    else None,
                    "price": str(item.price) if item.price is not None else None,
                    "store_name": store_lookup.get(item.store_id),
                    "notes": item.notes,
                    "barcode": item.barcode,
                    "image_path": image_path,
                }
            )
        return result, media_files

    def _export_meal_preferences(self, household):
        try:
            prefs = household.meal_preferences
        except MealPreferences.DoesNotExist:
            return None
        return {
            "cuisine_preferences": prefs.cuisine_preferences,
            "dietary_restrictions": prefs.dietary_restrictions,
            "cooking_effort": prefs.cooking_effort,
            "servings_per_meal": prefs.servings_per_meal,
            "excluded_ingredients": prefs.excluded_ingredients,
        }

    def _export_ai_settings(self, household):
        try:
            settings = household.ai_settings
        except AISettings.DoesNotExist:
            return None
        return {
            "model_bindings": settings.model_bindings,
            "openrouter_api_key_override": settings.openrouter_api_key_override,
            "usda_fdc_api_key_override": settings.usda_fdc_api_key_override,
        }

    def _export_meal_plans(self, household):
        plans = MealPlan.objects.filter(household=household).select_related("recipe")
        result = []
        for plan in plans.order_by("meal_date", "meal_type"):
            side_dishes = []
            for side in plan.side_dishes.select_related("recipe").order_by("order"):
                side_dishes.append(
                    {
                        "recipe_title": side.recipe.title if side.recipe else None,
                        "custom_side": side.custom_side,
                        "order": side.order,
                        "notes": side.notes,
                    }
                )

            result.append(
                {
                    "meal_date": plan.meal_date.isoformat(),
                    "meal_type": plan.meal_type,
                    "recipe_title": plan.recipe.title if plan.recipe else None,
                    "custom_meal": plan.custom_meal,
                    "notes": plan.notes,
                    "ingredients": plan.ingredients,
                    "meal_rating": plan.meal_rating,
                    "cooked_at": plan.cooked_at.isoformat() if plan.cooked_at else None,
                    "side_dishes": side_dishes,
                }
            )
        return result

    def _export_shopping_lists(self, household):
        weeks = ShoppingListWeek.objects.filter(household=household).prefetch_related(
            "items__source_recipe"
        )
        result = []
        for week in weeks.order_by("week_start"):
            items = []
            for item in week.items.order_by("checked", "category", "name"):
                items.append(
                    {
                        "name": item.name,
                        "quantity": str(item.quantity),
                        "unit": item.unit,
                        "category": item.category,
                        "checked": item.checked,
                        "recipe_title": item.source_recipe.title if item.source_recipe else None,
                        "notes": item.notes,
                    }
                )
            result.append(
                {
                    "week_start": week.week_start.isoformat(),
                    "items": items,
                }
            )
        return result

    def _export_ratings(self, household):
        from ratings.models import Rating

        return [
            {
                "recipe_title": rating.recipe.title,
                "username": rating.user.username,
                "score": rating.score,
                "notes": rating.notes,
            }
            for rating in Rating.objects.filter(recipe__household=household)
            .select_related("recipe", "user")
            .order_by("recipe__title", "user__username")
        ]


class ImportBackupView(LoginRequiredMixin, View):
    def post(self, request):
        uploaded = request.FILES.get("backup_file")
        if not uploaded:
            return JsonResponse(
                {"ok": False, "message": "No file uploaded."}, status=400
            )

        file_bytes = uploaded.read()
        archive = None

        try:
            zf = zipfile.ZipFile(io.BytesIO(file_bytes))
            json_data = zf.read("backup.json").decode("utf-8")
            data = json.loads(json_data)
            archive = zf
        except (zipfile.BadZipFile, KeyError):
            try:
                data = json.loads(file_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse(
                    {"ok": False, "message": "Invalid backup file. Expected ZIP or JSON."}, status=400
                )

        version = data.get("version")
        if version is None or version < 1 or version > BACKUP_VERSION:
            return JsonResponse(
                {
                    "ok": False,
                    "message": f"Unsupported backup version: {version}",
                },
                status=400,
            )

        household = request.user.household
        stats = {
            "recipes_imported": 0,
            "inventory_imported": 0,
            "meal_plans_imported": 0,
            "shopping_lists_imported": 0,
            "ratings_imported": 0,
            "skipped": 0,
        }

        self._import_stores(household, data.get("stores", []))
        self._import_inventory_categories(data.get("inventory_categories", []))
        self._import_ingredients(household, data.get("ingredients", []))
        recipe_title_to_id = self._import_recipes(
            household, data.get("recipes", []), archive, stats
        )
        self._import_meal_preferences(household, data.get("meal_preferences"))
        self._import_ai_settings(household, data.get("ai_settings"))
        self._import_meal_plans(
            household, data.get("meal_plans", []), recipe_title_to_id, stats
        )
        self._import_inventory(
            household, data.get("inventory", []), archive, stats
        )
        self._import_shopping_lists(
            household, data.get("shopping_lists", []), recipe_title_to_id, stats
        )
        self._import_ratings(
            household, data.get("ratings", []), recipe_title_to_id, request.user, stats
        )

        if archive:
            archive.close()

        return JsonResponse({"ok": True, "stats": stats})

    def _read_media(self, archive, path):
        if not archive or not path:
            return None
        try:
            return archive.read(path)
        except (KeyError, Exception):
            return None

    def _import_stores(self, household, stores_data):
        for store_data in stores_data:
            name = store_data.get("name", "").strip()
            if not name:
                continue
            Store.objects.update_or_create(
                household=household,
                name=name,
                defaults={"notes": store_data.get("notes", "")},
            )

    def _import_inventory_categories(self, categories_data):
        for category_data in categories_data:
            slug = category_data.get("slug", "").strip()
            if not slug:
                continue
            InventoryCategory.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": category_data.get("name", slug),
                    "sort_order": category_data.get("sort_order", 100),
                    "is_protected": category_data.get("is_protected", False),
                },
            )

    def _import_ingredients(self, household, ingredients_data):
        for ing_data in ingredients_data:
            name = ing_data.get("name", "").strip()
            if not name:
                continue
            Ingredient.objects.update_or_create(
                household=household,
                name=name,
                defaults={
                    "usda_food_id": ing_data.get("usda_food_id", ""),
                    "calories_kcal": ing_data.get("calories_kcal"),
                    "protein_g": ing_data.get("protein_g"),
                    "carbs_g": ing_data.get("carbs_g"),
                    "fat_g": ing_data.get("fat_g"),
                },
            )

    def _import_recipes(self, household, recipes_data, archive, stats):
        title_to_id = {}
        for recipe_data in recipes_data:
            title = recipe_data.get("title", "").strip()
            if not title:
                stats["skipped"] += 1
                continue

            existing = Recipe.objects.filter(household=household, title=title).first()
            if existing:
                title_to_id[title] = existing.pk
                stats["skipped"] += 1
                continue

            recipe = Recipe.objects.create(
                household=household,
                title=title,
                description=recipe_data.get("description", ""),
                video_url=recipe_data.get("video_url", ""),
                transcript_log=recipe_data.get("transcript_log", ""),
                on_hand_idea=recipe_data.get("on_hand_idea", False),
                leftover_worthy=recipe_data.get("leftover_worthy", False),
                needs_review=recipe_data.get("needs_review", True),
            )
            title_to_id[title] = recipe.pk

            photo_path = recipe_data.get("photo_path")
            photo_bytes = self._read_media(archive, photo_path)
            if photo_bytes:
                try:
                    filename = os.path.basename(photo_path) or f"recipe_{recipe.pk}.jpg"
                    recipe.photo.save(filename, ContentFile(photo_bytes), save=True)
                except Exception:
                    pass

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

            for inst_data in recipe_data.get("instructions", []):
                instruction = Instruction.objects.create(
                    recipe=recipe,
                    step_number=inst_data.get("step_number", 1),
                    text=inst_data.get("text", ""),
                )
                image_path = inst_data.get("image_path")
                image_bytes = self._read_media(archive, image_path)
                if image_bytes:
                    try:
                        filename = os.path.basename(image_path) or f"instruction_{instruction.pk}.jpg"
                        instruction.image.save(
                            filename, ContentFile(image_bytes), save=True
                        )
                    except Exception:
                        pass

            for tag_spec in recipe_data.get("tags", []):
                if isinstance(tag_spec, dict):
                    tag_name = tag_spec.get("name", "").strip()
                    tag_color = tag_spec.get("color", "#6B7280")
                else:
                    tag_name = str(tag_spec).strip()
                    tag_color = "#6B7280"
                if not tag_name:
                    continue
                # Tags are globally unique by name, so resolve by name first to
                # avoid cross-household unique-constraint collisions.
                tag, _ = Tag.objects.get_or_create(
                    name=tag_name,
                    defaults={"household": household, "color": tag_color},
                )
                tag.color = tag_color
                tag.save(update_fields=["color"])
                RecipeTag.objects.get_or_create(recipe=recipe, tag=tag)

            watch_session_data = recipe_data.get("watch_session")
            if watch_session_data:
                session = RecipeWatchSession.objects.create(
                    recipe=recipe,
                    status=watch_session_data.get("status", RecipeWatchSession.Status.PENDING),
                    error_message=watch_session_data.get("error_message", ""),
                )
                for seg_data in watch_session_data.get("segments", []):
                    segment = RecipeWatchSegment.objects.create(
                        session=session,
                        start_time=seg_data.get("start_time", "0"),
                        end_time=seg_data.get("end_time", "0"),
                        text=seg_data.get("text", ""),
                        step_number=seg_data.get("step_number"),
                    )
                    frame_path = seg_data.get("frame_path")
                    frame_bytes = self._read_media(archive, frame_path)
                    if frame_bytes:
                        try:
                            filename = os.path.basename(frame_path) or f"segment_{segment.pk}.jpg"
                            segment.image.save(
                                filename, ContentFile(frame_bytes), save=True
                            )
                        except Exception:
                            pass

            stats["recipes_imported"] += 1

        return title_to_id

    def _import_meal_preferences(self, household, prefs_data):
        if not prefs_data:
            return
        MealPreferences.objects.update_or_create(
            household=household,
            defaults={
                "cuisine_preferences": prefs_data.get("cuisine_preferences", []),
                "dietary_restrictions": prefs_data.get("dietary_restrictions", []),
                "cooking_effort": prefs_data.get("cooking_effort", "moderate"),
                "servings_per_meal": prefs_data.get("servings_per_meal", 2),
                "excluded_ingredients": prefs_data.get("excluded_ingredients", []),
            },
        )

    def _import_ai_settings(self, household, ai_data):
        if not ai_data:
            return
        AISettings.objects.update_or_create(
            household=household,
            defaults={
                "model_bindings": ai_data.get("model_bindings", {}),
                "openrouter_api_key_override": ai_data.get("openrouter_api_key_override", ""),
                "usda_fdc_api_key_override": ai_data.get("usda_fdc_api_key_override", ""),
            },
        )

    def _import_meal_plans(self, household, meal_plans_data, recipe_title_to_id, stats):
        for plan_data in meal_plans_data:
            meal_date = plan_data.get("meal_date")
            meal_type = plan_data.get("meal_type")
            if not meal_date or not meal_type:
                continue

            recipe_title = plan_data.get("recipe_title")
            recipe_id = recipe_title_to_id.get(recipe_title) if recipe_title else None
            if recipe_title and recipe_title not in recipe_title_to_id:
                # Try to find an existing recipe in the household
                recipe = Recipe.objects.filter(household=household, title=recipe_title).first()
                recipe_id = recipe.pk if recipe else None

            plan, created = MealPlan.objects.update_or_create(
                household=household,
                meal_date=meal_date,
                meal_type=meal_type,
                recipe_id=recipe_id,
                defaults={
                    "custom_meal": plan_data.get("custom_meal", ""),
                    "notes": plan_data.get("notes", ""),
                    "ingredients": plan_data.get("ingredients", []),
                    "meal_rating": plan_data.get("meal_rating"),
                    "cooked_at": plan_data.get("cooked_at"),
                },
            )
            if created:
                stats["meal_plans_imported"] += 1

            for side_data in plan_data.get("side_dishes", []):
                side_recipe_title = side_data.get("recipe_title")
                side_recipe_id = (
                    recipe_title_to_id.get(side_recipe_title) if side_recipe_title else None
                )
                if side_recipe_title and side_recipe_title not in recipe_title_to_id:
                    recipe = Recipe.objects.filter(household=household, title=side_recipe_title).first()
                    side_recipe_id = recipe.pk if recipe else None

                SideDish.objects.update_or_create(
                    meal_plan=plan,
                    recipe_id=side_recipe_id,
                    custom_side=side_data.get("custom_side", ""),
                    defaults={
                        "order": side_data.get("order", 0),
                        "notes": side_data.get("notes", ""),
                    },
                )

    def _import_inventory(self, household, inventory_data, archive, stats):
        store_name_to_id = {
            store.name: store.pk
            for store in Store.objects.filter(household=household)
        }

        for item_data in inventory_data:
            name = item_data.get("name", "").strip()
            if not name:
                stats["skipped"] += 1
                continue

            barcode = item_data.get("barcode", "")
            if barcode and InventoryItem.objects.filter(
                household=household, barcode=barcode
            ).exists():
                stats["skipped"] += 1
                continue

            store_name = item_data.get("store_name")
            store_id = store_name_to_id.get(store_name) if store_name else None

            item = InventoryItem.objects.create(
                household=household,
                name=name,
                quantity=item_data.get("quantity", "1"),
                unit=item_data.get("unit", "piece"),
                category=item_data.get("category", "other"),
                location=item_data.get("location", "pantry"),
                expiration_date=item_data.get("expiration_date") or None,
                price=item_data.get("price"),
                store_id=store_id,
                notes=item_data.get("notes", ""),
                barcode=barcode,
            )

            image_path = item_data.get("image_path")
            image_bytes = self._read_media(archive, image_path)
            if image_bytes:
                try:
                    filename = os.path.basename(image_path) or f"inventory_{item.pk}.jpg"
                    item.image.save(filename, ContentFile(image_bytes), save=True)
                except Exception:
                    pass

            stats["inventory_imported"] += 1

    def _import_shopping_lists(self, household, shopping_data, recipe_title_to_id, stats):
        for week_data in shopping_data:
            week_start = week_data.get("week_start")
            if not week_start:
                continue

            week, created = ShoppingListWeek.objects.update_or_create(
                household=household,
                week_start=week_start,
            )
            if created:
                stats["shopping_lists_imported"] += 1

            for item_data in week_data.get("items", []):
                recipe_title = item_data.get("recipe_title")
                recipe_id = (
                    recipe_title_to_id.get(recipe_title) if recipe_title else None
                )
                if recipe_title and recipe_title not in recipe_title_to_id:
                    recipe = Recipe.objects.filter(household=household, title=recipe_title).first()
                    recipe_id = recipe.pk if recipe else None

                ShoppingListItem.objects.update_or_create(
                    shopping_week=week,
                    name=item_data.get("name", "").strip(),
                    defaults={
                        "quantity": item_data.get("quantity", "1"),
                        "unit": item_data.get("unit", ""),
                        "category": item_data.get("category", "other"),
                        "checked": item_data.get("checked", False),
                        "source_recipe_id": recipe_id,
                        "notes": item_data.get("notes", ""),
                    },
                )

    def _import_ratings(self, household, ratings_data, recipe_title_to_id, user, stats):
        for rating_data in ratings_data:
            recipe_title = rating_data.get("recipe_title")
            if not recipe_title:
                continue

            recipe_id = recipe_title_to_id.get(recipe_title)
            if not recipe_id:
                recipe = Recipe.objects.filter(household=household, title=recipe_title).first()
                recipe_id = recipe.pk if recipe else None

            if not recipe_id:
                continue

            from ratings.models import Rating

            Rating.objects.update_or_create(
                recipe_id=recipe_id,
                user=user,
                defaults={
                    "score": rating_data.get("score", 1),
                    "notes": rating_data.get("notes", ""),
                },
            )
            stats["ratings_imported"] += 1

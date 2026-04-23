import re
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
)
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Avg, Q
from .models import Recipe
from .forms import RecipeForm, RatingForm, ImportForm
from .youtube import YouTubeService, InvalidVideoError, APIError
from .parsing import RecipeParsingService
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from tags.models import RecipeTag, Tag
from ratings.models import Rating


UNIT_CHOICES = [
    ("oz", "ounce"),
    ("lb", "pound"),
    ("cup", "cup"),
    ("tbsp", "tablespoon"),
    ("tsp", "teaspoon"),
    ("g", "gram"),
    ("kg", "kilogram"),
    ("ml", "milliliter"),
    ("l", "liter"),
    ("piece", "piece"),
    ("clove", "clove"),
    ("slice", "slice"),
    ("bunch", "bunch"),
    ("can", "can"),
]


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "recipes/recipe_list.html"
    context_object_name = "recipes"

    SORT_CHOICES = [
        ("newest", "Newest First"),
        ("oldest", "Oldest First"),
        ("rating", "Highest Rated"),
        ("title", "Title A-Z"),
    ]


class RecipeImportView(LoginRequiredMixin, FormView):
    form_class = ImportForm
    template_name = "recipes/import.html"
    success_url = reverse_lazy("recipes:recipe_create")

    SORT_CHOICES = [
        ("newest", "Newest First"),
        ("oldest", "Oldest First"),
        ("rating", "Highest Rated"),
        ("title", "Title A-Z"),
    ]

    def form_valid(self, form):
        youtube_url = form.cleaned_data["youtube_url"]

        api_key = getattr(settings, "YOUTUBE_API_KEY", None)
        if not api_key:
            form.add_error(
                "youtube_url", "YouTube API key not configured. Please contact support."
            )
            return self.form_invalid(form)

        try:
            youtube_service = YouTubeService(api_key)
            video_id = youtube_service.extract_video_id(youtube_url)
            metadata = youtube_service.get_video_metadata(video_id)

            parser = RecipeParsingService()

            # Try to get transcript for better content extraction
            full_text = metadata.description
            try:
                transcript = youtube_service.get_transcript(youtube_url)
                if transcript:
                    full_text = transcript
            except Exception:
                pass  # Fall back to description

            ingredients = parser.parse_ingredients(full_text)
            instructions = parser.parse_instructions(full_text)
            unparsed = parser.identify_unparseable(full_text.split("\n"))

            self.request.session["youtube_import"] = {
                "video_id": metadata.video_id,
                "title": metadata.title,
                "description": full_text,
                "thumbnail_url": metadata.thumbnail_url,
                "ingredients": [
                    {
                        "name": i.name,
                        "quantity": i.quantity,
                        "unit": i.unit,
                        "notes": i.notes,
                    }
                    for i in ingredients
                ],
                "instructions": [
                    {
                        "step_number": i.step_number,
                        "text": i.text,
                        "timestamp": i.timestamp,
                    }
                    for i in instructions
                ],
                "unparsed_lines": unparsed,
            }

            messages.success(
                self.request,
                f"Imported: {metadata.title} ({len(ingredients)} ingredients, {len(instructions)} steps)",
            )
            return redirect(self.success_url)

        except InvalidVideoError as e:
            form.add_error("youtube_url", str(e))
            return self.form_invalid(form)
        except APIError as e:
            form.add_error("youtube_url", str(e))
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(
                "youtube_url",
                "Could not fetch video. Please check the URL and try again.",
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{error}")
        return self.render_to_response(self.get_context_data(form=form))

    def get_queryset(self):
        queryset = Recipe.objects.filter(
            household=self.request.user.household, needs_review=False
        )

        search_q = self.request.GET.get("q")
        if search_q:
            queryset = queryset.filter(
                Q(title__icontains=search_q) | Q(description__icontains=search_q)
            )

        sort_by = self.request.GET.get("sort", "newest")
        if sort_by == "newest":
            queryset = queryset.order_by("-created_at")
        elif sort_by == "oldest":
            queryset = queryset.order_by("created_at")
        elif sort_by == "rating":
            queryset = queryset.annotate(avg_rating=Avg("rating__score")).order_by(
                "-avg_rating"
            )
        elif sort_by == "title":
            queryset = queryset.order_by("title")
        else:
            queryset = queryset.order_by("-created_at")

        return queryset.select_related("household").prefetch_related(
            "tags", "rating_set"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["sort"] = self.request.GET.get("sort", "newest")
        context["sort_choices"] = self.SORT_CHOICES
        return context


class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = "recipes/recipe_detail.html"

    def get_queryset(self):
        household = self.request.user.household
        if household:
            return Recipe.objects.filter(household=household) | Recipe.objects.filter(
                needs_review=True
            )
        return Recipe.objects.filter(needs_review=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.object

        context["ingredients"] = (
            IngredientLink.objects.filter(
                recipe=recipe,
                ingredient__household=self.request.user.household,
            )
            .select_related("ingredient", "inventory_item")
            .order_by("order")
        )

        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )

        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

        context["ratings"] = Rating.objects.filter(recipe=recipe)

        if context["ratings"].exists():
            avg = context["ratings"].values_list("score", flat=True)
            context["average_rating"] = sum(avg) / len(avg)
        else:
            context["average_rating"] = None

        existing_rating = Rating.objects.filter(
            recipe=recipe, user=self.request.user
        ).first()
        if existing_rating:
            context["rating_form"] = RatingForm(instance=existing_rating)
        else:
            context["rating_form"] = RatingForm()

        return context


class RecipeCreateView(LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unit_choices"] = UNIT_CHOICES

        youtube_import = self.request.session.get("youtube_import")
        if youtube_import:
            context["youtube_import"] = youtube_import
            context["has_youtube_import"] = True
            context["youtube_ingredients"] = youtube_import.get("ingredients", [])
            context["youtube_instructions"] = youtube_import.get("instructions", [])
            context["youtube_unparsed"] = youtube_import.get("unparsed_lines", [])

        return context

    def get_initial(self):
        initial = super().get_initial()
        youtube_import = self.request.session.get("youtube_import")
        if youtube_import:
            initial["title"] = youtube_import.get("title", "")
            initial["description"] = youtube_import.get("description", "")
        return initial

    def form_valid(self, form):
        youtube_import = self.request.session.get("youtube_import")

        form.instance.household = self.request.user.household
        recipe = form.save(commit=False)
        recipe.save()

        if youtube_import:
            ingredients = youtube_import.get("ingredients", [])
            for ing in ingredients:
                name = ing.get("name", "").strip()
                if name:
                    quantity = float(ing.get("quantity", 1)) or 1
                    unit = ing.get("unit", "piece") or "piece"

                    ing_obj, _ = Ingredient.objects.get_or_create(
                        household=recipe.household,
                        name__iexact=name,
                        defaults={"household": recipe.household, "name": name},
                    )
                    IngredientLink.objects.create(
                        recipe=recipe,
                        ingredient=ing_obj,
                        quantity=quantity,
                        unit=unit,
                    )

            instructions = youtube_import.get("instructions", [])
            for inst in instructions:
                text = inst.get("text", "").strip()
                if text:
                    step = inst.get("step_number", 1)
                    Instruction.objects.create(
                        recipe=recipe,
                        step_number=step,
                        text=text,
                    )

            del self.request.session["youtube_import"]
            messages.success(
                self.request, f"Recipe '{recipe.title}' created from YouTube import!"
            )
        else:
            self._save_ingredients(recipe)
            self._save_instructions(recipe)
            messages.success(self.request, f"Recipe '{recipe.title}' created!")

        return redirect("recipes:recipe_detail", pk=recipe.pk)

    def _save_ingredients(self, recipe):
        names = self.request.POST.getlist("ingredient_name")
        quantities = self.request.POST.getlist("ingredient_quantity")
        units = self.request.POST.getlist("ingredient_unit")

        for i, name in enumerate(names):
            name = name.strip()
            if name:
                quantity = (
                    float(quantities[i]) if i < len(quantities) and quantities[i] else 1
                )
                unit = units[i] if i < len(units) and units[i] else "piece"

                ing, _ = Ingredient.objects.get_or_create(
                    household=recipe.household,
                    name__iexact=name,
                    defaults={"household": recipe.household, "name": name},
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ing,
                    quantity=quantity,
                    unit=unit,
                )

    def _save_instructions(self, recipe):
        texts = self.request.POST.getlist("instruction_text")
        orders = self.request.POST.getlist("instruction_step")

        for i, text in enumerate(texts):
            text = text.strip()
            if text:
                order = int(orders[i]) if i < len(orders) and orders[i] else i + 1
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=order,
                    text=text,
                )


class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unit_choices"] = UNIT_CHOICES
        recipe = self.object

        context["ingredients"] = IngredientLink.objects.filter(
            recipe=recipe
        ).select_related("ingredient")
        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )
        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")
        context["available_tags"] = Tag.objects.filter(
            household=self.request.user.household
        )

        return context

    def form_valid(self, form):
        recipe = form.save(commit=False)
        recipe.save()

        IngredientLink.objects.filter(recipe=recipe).delete()
        self._save_ingredients(recipe)

        Instruction.objects.filter(recipe=recipe).delete()
        self._save_instructions(recipe)

        return redirect("recipes:recipe_detail", pk=recipe.pk)

    def _save_ingredients(self, recipe):
        names = self.request.POST.getlist("ingredient_name")
        quantities = self.request.POST.getlist("ingredient_quantity")
        units = self.request.POST.getlist("ingredient_unit")

        for i, name in enumerate(names):
            name = name.strip()
            if name:
                quantity = (
                    float(quantities[i]) if i < len(quantities) and quantities[i] else 1
                )
                unit = units[i] if i < len(units) and units[i] else "piece"

                ing, _ = Ingredient.objects.get_or_create(
                    household=recipe.household,
                    name__iexact=name,
                    defaults={"household": recipe.household, "name": name},
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ing,
                    quantity=quantity,
                    unit=unit,
                )

    def _save_instructions(self, recipe):
        texts = self.request.POST.getlist("instruction_text")
        orders = self.request.POST.getlist("instruction_step")

        for i, text in enumerate(texts):
            text = text.strip()
            if text:
                order = int(orders[i]) if i < len(orders) and orders[i] else i + 1
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=order,
                    text=text,
                )


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = "recipes/recipe_confirm_delete.html"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)


@require_POST
def recipe_rate_view(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, household=request.user.household)

    existing_rating = Rating.objects.filter(recipe=recipe, user=request.user).first()

    if existing_rating:
        form = RatingForm(request.POST, instance=existing_rating)
    else:
        form = RatingForm(request.POST)

    if form.is_valid():
        rating = form.save(commit=False)
        rating.recipe = recipe
        rating.user = request.user
        rating.save()
        messages.success(request, "Rating saved!")

    return redirect("recipes:recipe_detail", pk=pk)

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
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Avg, Q
from .models import Recipe
from .forms import RecipeForm, RatingForm, ImportForm
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
    success_url = reverse_lazy("recipe_create")

    def form_valid(self, form):
        url = form.cleaned_data.get("youtube_url", "")
        messages.success(
            self.request,
            f"Found: {url}. Import functionality coming in later phases.",
        )
        return redirect(self.success_url)

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
        return Recipe.objects.filter(household=self.request.user.household)

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
        return context

    def form_valid(self, form):
        form.instance.household = self.request.user.household
        recipe = form.save(commit=False)
        recipe.save()

        self._save_ingredients(recipe)
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

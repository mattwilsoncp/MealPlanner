from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Recipe
from .forms import RecipeForm, RatingForm
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from tags.models import RecipeTag, Tag
from ratings.models import Rating


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "recipes/recipe_list.html"
    context_object_name = "recipes"

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)


class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = "recipes/recipe_detail.html"

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.object

        # Get ingredients for this recipe
        context["ingredients"] = IngredientLink.objects.filter(
            recipe=recipe
        ).select_related("ingredient", "inventory_item")

        # Get instructions for this recipe
        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )

        # Get tags for this recipe
        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

        # Get ratings for this recipe
        context["ratings"] = Rating.objects.filter(recipe=recipe)

        # Compute average rating
        if context["ratings"].exists():
            avg = context["ratings"].values_list("score", flat=True)
            context["average_rating"] = sum(avg) / len(avg)
        else:
            context["average_rating"] = None

        # Add rating form if user hasn't rated yet
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

    def form_valid(self, form):
        form.instance.household = self.request.user.household
        return super().form_valid(form)


class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.object

        # Get existing ingredients
        context["ingredients"] = IngredientLink.objects.filter(
            recipe=recipe
        ).select_related("ingredient")

        # Get existing instructions
        context["instructions"] = Instruction.objects.filter(recipe=recipe).order_by(
            "step_number"
        )

        # Get existing tags
        context["tags"] = RecipeTag.objects.filter(recipe=recipe).select_related("tag")

        # Get available tags for household
        context["available_tags"] = Tag.objects.filter(
            household=self.request.user.household
        )

        return context


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    model = Recipe
    template_name = "recipes/recipe_confirm_delete.html"
    success_url = reverse_lazy("recipes:recipe_list")

    def get_queryset(self):
        return Recipe.objects.filter(household=self.request.user.household)


@require_POST
def recipe_rate_view(request, pk):
    """Handle rating a recipe (upsert behavior)."""
    recipe = get_object_or_404(Recipe, pk=pk, household=request.user.household)

    # Check if user already rated this recipe
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

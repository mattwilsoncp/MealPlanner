from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, UpdateView, RedirectView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from recipes.models import Recipe
from ingredients.models import IngredientLink
from ingredients.forms import IngredientLinkReconciliationForm
from inventory.models import InventoryItem


class ReviewQueueView(LoginRequiredMixin, ListView):
    """List all recipes that need review for the user's household."""

    model = Recipe
    template_name = "reviews/review_queue.html"
    context_object_name = "needs_review"

    def get_queryset(self):
        return Recipe.objects.filter(
            household=self.request.user.household, needs_review=True
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recipes"] = context["needs_review"]
        return context


class MarkReadyView(LoginRequiredMixin, UpdateView):
    """Mark a recipe as ready (needs_review=False)."""

    model = Recipe
    fields = []
    template_name = "reviews/mark_ready.html"
    success_url = reverse_lazy("reviews:review_queue")

    def get_queryset(self):
        return Recipe.objects.filter(
            household=self.request.user.household, needs_review=True
        )

    def form_valid(self, form):
        form.instance.needs_review = False
        return super().form_valid(form)


class RecipeReconcileView(LoginRequiredMixin, DetailView):
    """Show recipe detail for ingredient reconciliation."""

    model = Recipe
    template_name = "reviews/reconcile.html"

    def get_queryset(self):
        return Recipe.objects.filter(
            household=self.request.user.household, needs_review=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.get_object()
        # Get ingredient links with their current inventory assignments
        context["ingredient_links"] = recipe.ingredients.all().select_related(
            "ingredient"
        )
        # Get all inventory items for the household for dropdown
        context["inventory_items"] = InventoryItem.objects.filter(
            household=self.request.user.household
        ).order_by("name")
        return context


class SaveReconciliationView(LoginRequiredMixin, UpdateView):
    """Save ingredient-to-inventory links."""

    model = Recipe
    fields = []
    template_name = "reviews/reconcile.html"
    success_url = reverse_lazy("reviews:review_queue")

    def get_queryset(self):
        return Recipe.objects.filter(
            household=self.request.user.household, needs_review=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.get_object()
        context["ingredient_links"] = recipe.ingredients.all().select_related(
            "ingredient"
        )
        context["inventory_items"] = InventoryItem.objects.filter(
            household=self.request.user.household
        ).order_by("name")
        return context

    def post(self, request, *args, **kwargs):
        recipe = self.get_object()
        # Process each ingredient link's inventory assignment
        for ingredient_link in recipe.ingredients.all():
            link_id = ingredient_link.id
            form = IngredientLinkReconciliationForm(
                {
                    "inventory_item_id": request.POST.get(
                        f"inventory_item_{link_id}", ""
                    )
                },
                household=request.user.household,
            )
            if form.is_valid():
                ingredient_link.inventory_item = form.cleaned_data["inventory_item_id"]
            ingredient_link.save()
        # Optionally mark as ready if requested
        if request.POST.get("mark_ready"):
            recipe.needs_review = False
            recipe.save()

        messages.success(request, "Ingredient links saved successfully.")
        return redirect(reverse_lazy("reviews:review_queue"))

from django.db import models
from household.models import Household


class Ingredient(models.Model):
    """Canonical ingredient name, scoped to household."""

    name = models.CharField(max_length=100, db_index=True)
    household = models.ForeignKey(Household, on_delete=models.CASCADE)
    usda_food_id = models.CharField(
        max_length=20, blank=True
    )  # USDA FoodData Central ID
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["household", "name"]
        ordering = ["name"]

    def __str__(self):
        return self.name


class IngredientLink(models.Model):
    """Link between a recipe and an ingredient with quantity/unit."""

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

    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=6, decimal_places=2)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    order = models.PositiveIntegerField(default=0)
    # inventory_item = models.ForeignKey(
    #     "inventory.InventoryItem",
    #     null=True,
    #     blank=True,
    #     on_delete=models.SET_NULL,
    # )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.ingredient.name}"

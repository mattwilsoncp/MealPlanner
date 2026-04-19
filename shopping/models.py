from django.db import models

from household.models import Household
from recipes.models import Recipe


class ShoppingListWeek(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="shopping_weeks"
    )
    week_start = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["household", "week_start"],
                name="shopping_unique_household_week",
            )
        ]
        indexes = [
            models.Index(fields=["household", "week_start"]),
            models.Index(fields=["household", "-week_start"]),
        ]

    def __str__(self):
        return f"{self.household} - Week of {self.week_start}"


class ShoppingListItem(models.Model):
    shopping_week = models.ForeignKey(
        ShoppingListWeek, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=200, db_index=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, blank=True)
    category = models.CharField(max_length=50, default="other", blank=True)
    checked = models.BooleanField(default=False)
    source_recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shopping_items",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["checked", "category", "name"]
        indexes = [
            models.Index(fields=["shopping_week", "checked"]),
            models.Index(fields=["shopping_week", "category"]),
        ]

    def __str__(self):
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.quantity}{unit} {self.name}".strip()

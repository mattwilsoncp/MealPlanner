from django.db import models
from django.conf import settings
from household.models import Household
from recipes.models import Recipe


class MealType(models.TextChoices):
    BREAKFAST = "breakfast", "Breakfast"
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"
    SNACK = "snack", "Snack"


class MealPlan(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="meal_plans"
    )
    meal_date = models.DateField(db_index=True)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_plans",
    )
    custom_meal = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    meal_rating = models.IntegerField(blank=True, null=True)  # 1-5 scale
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["meal_date", "meal_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["household", "meal_date", "meal_type", "recipe"],
                name="unique_meal_per_type",
            )
        ]
        indexes = [
            models.Index(fields=["household", "meal_date"]),
            models.Index(fields=["meal_date", "meal_type"]),
        ]

    def __str__(self):
        meal_name = self.recipe.title if self.recipe else self.custom_meal or "No meal"
        return f"{self.meal_date} - {self.get_meal_type_display()} - {meal_name}"

    @property
    def is_custom(self):
        return self.recipe is None

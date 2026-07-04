from django.db import models
from django.conf import settings
from household.models import Household
from recipes.models import Recipe


class CookingEffort(models.TextChoices):
    QUICK = "quick", "Quick (<30 min)"
    MODERATE = "moderate", "Moderate (30-60 min)"
    ELABORATE = "elaborate", "Elaborate (>60 min)"


class MealPreferences(models.Model):
    household = models.OneToOneField(
        Household, on_delete=models.CASCADE, related_name="meal_preferences"
    )
    cuisine_preferences = models.JSONField(
        default=list, blank=True
    )
    dietary_restrictions = models.JSONField(
        default=list, blank=True
    )
    cooking_effort = models.CharField(
        max_length=20, choices=CookingEffort.choices, default="moderate"
    )
    servings_per_meal = models.PositiveSmallIntegerField(default=2)
    excluded_ingredients = models.JSONField(
        default=list, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "meal preferences"

    def __str__(self):
        return f"Meal preferences for {self.household}"


class AISettings(models.Model):
    """Per-household AI model preferences and API key overrides.

    ``model_bindings`` is a JSONField keyed by feature slug (see
    ``meal_planner_app.services.ai_settings.FEATURE_KEYS``). Each value is::

        {"model_id": "<openrouter id>", "label": "<display name>", "updated_at": "<iso8601>"}

    ``openrouter_api_key_override`` is the per-household OpenRouter key,
    used when the household wants to bill AI calls to their own account
    instead of the shared server-wide ``OPENROUTER_API_KEY`` env value.
    Empty falls back to the env value.

    ``usda_fdc_api_key_override`` is the per-household USDA FoodData
    Central API key, used when the household wants ingredient lookups
    to bill against their own FDC account instead of the shared
    ``USDA_FDC_API_KEY`` env value (which defaults to ``"DEMO_KEY"`` so
    the link-from-recipe flow works out of the box for development).
    Empty falls back to the env value.
    """

    household = models.OneToOneField(
        Household, on_delete=models.CASCADE, related_name="ai_settings"
    )
    model_bindings = models.JSONField(default=dict, blank=True)
    openrouter_api_key_override = models.CharField(
        max_length=255, blank=True, default=""
    )
    usda_fdc_api_key_override = models.CharField(
        max_length=255, blank=True, default=""
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI settings"
        verbose_name_plural = "AI settings"

    def __str__(self):
        return f"AI settings for {self.household}"

    def set_model(self, feature_key: str, model_id: str, label: str = "") -> None:
        """Persist the chosen model for ``feature_key``."""
        import datetime as _dt

        data = dict(self.model_bindings or {})
        data[feature_key] = {
            "model_id": model_id,
            "label": label,
            "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.model_bindings = data
        self.save(update_fields=["model_bindings", "updated_at"])

    def get_model(self, feature_key: str) -> dict | None:
        """Return the saved binding for ``feature_key`` or ``None``."""
        if not self.model_bindings:
            return None
        value = self.model_bindings.get(feature_key)
        return value if isinstance(value, dict) else None


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
    ingredients = models.JSONField(default=list, blank=True)
    meal_rating = models.IntegerField(blank=True, null=True)  # 1-5 scale
    cooked_at = models.DateTimeField(blank=True, null=True)  # When meal was cooked
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


class SideDish(models.Model):
    """Side dishes linked to a meal plan entry."""

    meal_plan = models.ForeignKey(
        MealPlan, on_delete=models.CASCADE, related_name="side_dishes"
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="as_side_dish",
    )
    custom_side = models.CharField(max_length=200, null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.recipe.title if self.recipe else self.custom_side or "Side dish"

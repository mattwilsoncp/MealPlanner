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

    # The save-signature for AI meal-plan writes
    # (``meal_planner_app.views.AiPlanSaveView``) is
    # ``notes="AI-generated | Cook time: {cook_time} min"``. Keep this
    # constant in sync if you ever change that string in the save view —
    # the planner card, the promote-to-recipe view, and the unit tests
    # all read from the same marker.
    AI_GENERATED_NOTES_PREFIX = "AI-generated | Cook time:"

    @property
    def is_ai_generated(self) -> bool:
        """True when the meal was materialized from an accepted AI plan.

        Recognised by the ``notes`` prefix written by
        ``AiPlanSaveView``. Custom-meal cards use this to surface an
        "AI" badge on the planner that links to the
        ``promote_meal_to_recipe`` page; once the meal is converted
        into a real Recipe (or the prefix is cleared), the badge
        disappears automatically.
        """
        notes = (self.notes or "").lstrip()
        return notes.startswith(self.AI_GENERATED_NOTES_PREFIX)

    @property
    def ai_cook_time_minutes(self) -> int | None:
        """Cook-time saved on the AI meal, or ``None`` if not AI.

        Mirrors ``AiPlanSaveView``'s ``notes`` formatting. Returns
        ``None`` for non-AI meals so callers can fall back to a
        sensible default.
        """
        notes = (self.notes or "").lstrip()
        if not notes.startswith(self.AI_GENERATED_NOTES_PREFIX):
            return None
        # Format: "AI-generated | Cook time: 30 min"
        try:
            tail = notes[len(self.AI_GENERATED_NOTES_PREFIX):]
            # Skip leading separator and word "Cook" (already matched).
            tail = tail.strip(" :")
            # Strip suffix "min" / "minutes" if present.
            tail = tail.split(" ", 1)[0]
            return int(tail)
        except (ValueError, IndexError):
            return None

    @property
    def ai_title(self) -> str:
        """Strip the ``"{title}: {description}"`` shape used by
        ``AiPlanSaveView`` so the promote-to-recipe page can show
        just the title. Falls back to ``custom_meal`` when no
        separator is present.
        """
        if not self.is_ai_generated:
            return self.custom_meal or ""
        text = (self.custom_meal or "").strip()
        if ":" in text:
            return text.split(":", 1)[0].strip()
        return text

    @property
    def ai_description(self) -> str:
        """Description portion of the AI meal's ``custom_meal`` blob.

        ``AiPlanSaveView`` writes ``custom_meal="<title>: <description>"``
        — everything after the first colon is the description. Returns
        ``""`` for non-AI meals.
        """
        if not self.is_ai_generated:
            return ""
        text = (self.custom_meal or "").strip()
        if ":" not in text:
            return ""
        return text.split(":", 1)[1].strip()


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

from django import forms
from django.forms import modelform_factory, modelformset_factory

from .models import MealPlan, MealType, SideDish, MealPreferences, CookingEffort
from recipes.models import Recipe


CUISINE_CHOICES = [
    ("italian", "Italian"),
    ("mexican", "Mexican"),
    ("asian", "Asian"),
    ("american", "American"),
    ("mediterranean", "Mediterranean"),
    ("indian", "Indian"),
    ("japanese", "Japanese"),
    ("thai", "Thai"),
    ("greek", "Greek"),
    ("french", "French"),
    ("korean", "Korean"),
    ("middle-eastern", "Middle Eastern"),
    ("southern", "Southern"),
    ("caribbean", "Caribbean"),
    ("cajun", "Cajun"),
    ("german", "German"),
    ("vietnamese", "Vietnamese"),
    ("brazilian", "Brazilian"),
    ("spanish", "Spanish"),
    ("moroccan", "Moroccan"),
]

DIETARY_CHOICES = [
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("gluten-free", "Gluten-Free"),
    ("dairy-free", "Dairy-Free"),
    ("low-carb", "Low-Carb"),
    ("keto", "Keto"),
    ("nut-free", "Nut-Free"),
    ("egg-free", "Egg-Free"),
    ("soy-free", "Soy-Free"),
    ("pescatarian", "Pescatarian"),
]


class MealPreferencesForm(forms.ModelForm):
    """Form for configuring meal planning preferences."""

    cuisine_preferences = forms.MultipleChoiceField(
        choices=CUISINE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Cuisine Preferences",
    )
    dietary_restrictions = forms.MultipleChoiceField(
        choices=DIETARY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Dietary Restrictions",
    )
    cooking_effort = forms.ChoiceField(
        choices=CookingEffort.choices,
        widget=forms.RadioSelect,
        required=True,
        label="Cooking Effort",
    )
    servings_per_meal = forms.IntegerField(
        min_value=1,
        max_value=8,
        widget=forms.NumberInput(
            attrs={"class": "input input-bordered w-20", "min": 1, "max": 8}
        ),
        label="Servings Per Meal",
    )
    excluded_ingredients = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "e.g., mushrooms, cilantro, anchovies",
            }
        ),
        required=False,
        label="Excluded Ingredients",
        help_text="Comma-separated list of ingredients to exclude",
    )

    class Meta:
        model = MealPreferences
        fields = [
            "cuisine_preferences",
            "dietary_restrictions",
            "cooking_effort",
            "servings_per_meal",
            "excluded_ingredients",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Convert list values back to checkbox-friendly format
        if self.instance.pk:
            if self.instance.cuisine_preferences:
                self.initial["cuisine_preferences"] = self.instance.cuisine_preferences
            if self.instance.dietary_restrictions:
                self.initial["dietary_restrictions"] = self.instance.dietary_restrictions
            if self.instance.excluded_ingredients:
                self.initial["excluded_ingredients"] = ", ".join(
                    self.instance.excluded_ingredients
                )

    def clean_excluded_ingredients(self):
        """Split comma-separated string into a list."""
        value = self.cleaned_data.get("excluded_ingredients", "")
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


class MealPlanForm(forms.ModelForm):
    """Form for adding and editing meal plan entries."""

    class Meta:
        model = MealPlan
        fields = ["meal_date", "meal_type", "recipe", "custom_meal", "notes"]
        widgets = {
            "meal_date": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered"}
            ),
            "meal_type": forms.Select(attrs={"class": "select select-bordered"}),
            "recipe": forms.Select(attrs={"class": "select select-bordered"}),
            "custom_meal": forms.TextInput(
                attrs={
                    "class": "input input-bordered",
                    "placeholder": "Enter custom meal name",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered",
                    "placeholder": "Optional notes...",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Filter recipe queryset to user's recipes not needing review
        if self.request and hasattr(self.request, "user"):
            self.fields["recipe"].queryset = self.request.user.household.recipes.filter(
                needs_review=False
            ).order_by("title")
        else:
            self.fields["recipe"].queryset = Recipe.objects.none()

    def clean(self):
        """Validate that either recipe or custom_meal is provided."""
        cleaned_data = super().clean()
        recipe = cleaned_data.get("recipe")
        custom_meal = cleaned_data.get("custom_meal")

        if not recipe and not custom_meal:
            raise forms.ValidationError(
                "Please select a recipe or enter a custom meal name."
            )

        return cleaned_data


class SideDishForm(forms.ModelForm):
    """Form for adding side dishes to a meal plan entry."""

    class Meta:
        model = SideDish
        fields = ["recipe", "custom_side", "order", "notes"]
        widgets = {
            "recipe": forms.Select(attrs={"class": "select select-bordered"}),
            "custom_side": forms.TextInput(
                attrs={
                    "class": "input input-bordered",
                    "placeholder": "Or enter custom side dish",
                }
            ),
            "order": forms.NumberInput(attrs={"class": "input input-bordered w-16"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered",
                    "placeholder": "Optional notes...",
                    "rows": 2,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Filter recipe queryset to user's recipes not needing review
        if self.request and hasattr(self.request, "user"):
            self.fields["recipe"].queryset = self.request.user.household.recipes.filter(
                needs_review=False
            ).order_by("title")
        else:
            self.fields["recipe"].queryset = Recipe.objects.none()


# Inline formset for side dishes
SideDishFormSet = modelformset_factory(
    SideDish, form=SideDishForm, extra=1, can_delete=True
)

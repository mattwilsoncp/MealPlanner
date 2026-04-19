from django import forms
from .models import MealPlan, MealType


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

        # Filter recipe queryset to user's recipes
        if self.request and hasattr(self.request, "user"):
            self.fields["recipe"].queryset = self.request.user.household.recipes.all()
        else:
            self.fields["recipe"].queryset = None

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

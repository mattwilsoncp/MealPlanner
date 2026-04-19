from django import forms
from django.forms import formset_factory
from .models import Recipe
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from tags.models import RecipeTag, Tag
from ratings.models import Rating


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = [
            "title",
            "description",
            "photo",
            "video_url",
            "on_hand_idea",
            "leftover_worthy",
            "needs_review",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class IngredientLinkForm(forms.ModelForm):
    """Form for adding/editing an ingredient link."""

    class Meta:
        model = IngredientLink
        fields = ["ingredient", "quantity", "unit", "order"]
        widgets = {
            "ingredient": forms.TextInput(attrs={"placeholder": "Ingredient name"}),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }


class InstructionForm(forms.ModelForm):
    """Form for adding/editing an instruction step."""

    class Meta:
        model = Instruction
        fields = ["step_number", "text", "image"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }


class TagForm(forms.ModelForm):
    """Form for creating/editing a tag."""

    class Meta:
        model = Tag
        fields = ["name", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Tag name"}),
            "color": forms.TextInput(attrs={"type": "color"}),
        }


class RatingForm(forms.ModelForm):
    """Form for rating a recipe."""

    class Meta:
        model = Rating
        fields = ["score", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes"}),
        }


# Create formsets
IngredientLinkFormSet = formset_factory(IngredientLinkForm, extra=1, can_delete=True)
InstructionFormSet = formset_factory(InstructionForm, extra=1, can_delete=True)

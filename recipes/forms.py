from django import forms
from .models import Recipe


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

from django import forms
from django.forms import formset_factory
import re

from .models import Recipe
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from tags.models import RecipeTag, Tag
from ratings.models import Rating


class ImportForm(forms.Form):
    youtube_url = forms.URLField(
        label="YouTube URL",
        widget=forms.URLInput(
            attrs={
                "class": "input-dark",
                "placeholder": "https://youtube.com/watch?v=... or https://youtu.be/...",
            }
        ),
    )

    def clean_youtube_url(self):
        url = self.cleaned_data.get("youtube_url", "")
        if url and not self._is_youtube_url(url):
            raise forms.ValidationError(
                "Please enter a valid YouTube URL (youtube.com or youtu.be)"
            )
        return url

    def _is_youtube_url(self, url):
        return "youtube.com" in url or "youtu.be" in url


class LLMImportForm(forms.Form):
    youtube_url = forms.URLField(
        label="YouTube URL",
        widget=forms.URLInput(
            attrs={
                "class": "input-dark",
                "placeholder": "https://youtube.com/watch?v=... or https://youtu.be/...",
            }
        ),
    )
    model = forms.ChoiceField(
        label="AI Model",
        choices=[
            ("qwen/qwen-turbo", "Qwen Turbo (Fast, Free)"),
            ("qwen/qwen-plus", "Qwen Plus"),
            ("anthropic/claude-sonnet-4-20250514", "Claude Sonnet"),
        ],
        initial="qwen/qwen-turbo",
        required=False,
        widget=forms.Select(attrs={"class": "input-dark"}),
    )

    def clean_youtube_url(self):
        url = self.cleaned_data.get("youtube_url", "")
        if url and not self._is_youtube_url(url):
            raise forms.ValidationError(
                "Please enter a valid YouTube URL (youtube.com or youtu.be)"
            )
        return url

    def _is_youtube_url(self, url):
        return "youtube.com" in url or "youtu.be" in url


class RecipeForm(forms.ModelForm):
    new_tag_name = forms.CharField(required=False, max_length=50)
    new_tag_color = forms.CharField(required=False, max_length=7, initial="#6B7280")

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
            "title": forms.TextInput(
                attrs={"class": "input-dark", "placeholder": "Recipe title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "input-dark",
                    "rows": 4,
                    "placeholder": "Brief description",
                }
            ),
            "photo": forms.FileInput(
                attrs={"class": "input-dark", "accept": "image/*"}
            ),
            "video_url": forms.URLInput(
                attrs={
                    "class": "input-dark",
                    "placeholder": "https://youtube.com/watch?v=...",
                }
            ),
            "on_hand_idea": forms.CheckboxInput(attrs={"class": "w-5 h-5"}),
            "leftover_worthy": forms.CheckboxInput(attrs={"class": "w-5 h-5"}),
            "needs_review": forms.CheckboxInput(attrs={"class": "w-5 h-5"}),
        }

    def clean_new_tag_name(self):
        raw_value = self.data.get("new_tag_name", "")
        normalized = " ".join((raw_value or "").strip().split())

        if raw_value and not normalized:
            raise forms.ValidationError("New tag name cannot be empty.")

        household = getattr(self.instance, "household", None)
        if normalized and household:
            duplicate_exists = Tag.objects.filter(
                household=household,
                name__iexact=normalized,
            ).exists()
            if duplicate_exists:
                raise forms.ValidationError(
                    "A tag with this name already exists for your household."
                )

        return normalized

    def clean(self):
        cleaned_data = super().clean()
        self._instruction_order_map = {}

        for key, value in self.data.items():
            match = re.fullmatch(r"instruction_(\d+)_order", key)
            if not match:
                continue

            instruction_id = int(match.group(1))
            try:
                order_value = int(value)
            except (TypeError, ValueError):
                self.add_error(None, "Instruction order must be an integer.")
                continue

            self._instruction_order_map[instruction_id] = order_value

        return cleaned_data

    def save(self, commit=True):
        recipe = super().save(commit=commit)

        if commit and recipe.pk:
            self._save_instruction_order(recipe)
            self._save_recipe_tags(recipe)

        return recipe

    def _save_instruction_order(self, recipe):
        posted_order = getattr(self, "_instruction_order_map", {})
        current_instructions = list(
            Instruction.objects.filter(recipe=recipe).order_by("step_number", "id")
        )
        if not current_instructions:
            return

        instruction_by_id = {
            instruction.id: instruction for instruction in current_instructions
        }
        sorted_ids = [
            instruction_id
            for instruction_id, _ in sorted(
                posted_order.items(), key=lambda item: (item[1], item[0])
            )
            if instruction_id in instruction_by_id
        ]

        ordered_instructions = [
            instruction_by_id[instruction_id] for instruction_id in sorted_ids
        ]
        ordered_instructions.extend(
            [
                instruction
                for instruction in current_instructions
                if instruction.id not in set(sorted_ids)
            ]
        )

        for step_number, instruction in enumerate(ordered_instructions, start=1):
            if instruction.step_number != step_number:
                instruction.step_number = step_number
                instruction.save(update_fields=["step_number"])

    def _save_recipe_tags(self, recipe):
        selected_tag_ids = []
        for tag_id in self.data.getlist("tags"):
            try:
                selected_tag_ids.append(int(tag_id))
            except (TypeError, ValueError):
                continue

        valid_tags = Tag.objects.filter(
            household=recipe.household,
            id__in=selected_tag_ids,
        )
        valid_tag_ids = list(valid_tags.values_list("id", flat=True))

        RecipeTag.objects.filter(recipe=recipe).exclude(
            tag_id__in=valid_tag_ids
        ).delete()
        for tag_id in valid_tag_ids:
            RecipeTag.objects.get_or_create(recipe=recipe, tag_id=tag_id)

        new_tag_name = self.cleaned_data.get("new_tag_name", "")
        if new_tag_name:
            tag_color = self.cleaned_data.get("new_tag_color") or "#6B7280"
            created_tag = Tag.objects.create(
                household=recipe.household,
                name=new_tag_name,
                color=tag_color,
            )
            RecipeTag.objects.get_or_create(recipe=recipe, tag=created_tag)


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

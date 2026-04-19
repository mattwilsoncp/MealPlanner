from django import forms

from ingredients.models import Ingredient
from inventory.models import InventoryItem


class IngredientNutritionForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = [
            "usda_food_id",
            "calories_kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
        ]

    def clean_usda_food_id(self):
        usda_food_id = (self.cleaned_data.get("usda_food_id") or "").strip()
        if usda_food_id and len(usda_food_id) > 20:
            raise forms.ValidationError(
                "USDA reference ID must be 20 characters or fewer."
            )
        return usda_food_id


class IngredientLinkReconciliationForm(forms.Form):
    inventory_item_id = forms.CharField(required=False)

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.household = household

    def clean_inventory_item_id(self):
        inventory_item_id = (self.cleaned_data.get("inventory_item_id") or "").strip()
        if not inventory_item_id or inventory_item_id == "none":
            return None

        try:
            item = InventoryItem.objects.get(id=inventory_item_id)
        except (InventoryItem.DoesNotExist, ValueError):
            raise forms.ValidationError("Select a valid inventory item.")

        if self.household and item.household_id != self.household.id:
            raise forms.ValidationError(
                "Inventory item does not belong to your household."
            )

        return item

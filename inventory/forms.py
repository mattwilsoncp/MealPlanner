from django import forms

from .models import InventoryItem


class BaseInventoryItemForm(forms.ModelForm):
    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")

        if quantity is not None and quantity < 0:
            raise forms.ValidationError("Quantity cannot be negative.")

        return quantity


class InventoryItemForm(BaseInventoryItemForm):
    class Meta:
        model = InventoryItem
        fields = [
            "name",
            "quantity",
            "unit",
            "category",
            "location",
            "expiration_date",
            "notes",
            "image",
            "barcode",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered"}),
            "quantity": forms.NumberInput(
                attrs={"class": "input input-bordered", "step": "0.01", "min": "0"}
            ),
            "unit": forms.Select(attrs={"class": "select select-bordered"}),
            "category": forms.Select(attrs={"class": "select select-bordered"}),
            "location": forms.Select(attrs={"class": "select select-bordered"}),
            "expiration_date": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered"}
            ),
            "notes": forms.Textarea(attrs={"class": "textarea textarea-bordered"}),
            "image": forms.ClearableFileInput(
                attrs={"class": "file-input file-input-bordered"}
            ),
            "barcode": forms.TextInput(attrs={"class": "input input-bordered"}),
        }


class InventoryQuickAddForm(BaseInventoryItemForm):
    class Meta(InventoryItemForm.Meta):
        pass


class ReceiptImportForm(forms.Form):
    image = forms.ImageField(
        label="Receipt Photo",
        widget=forms.FileInput(
            attrs={
                "class": "input-dark",
                "accept": "image/*",
                "capture": "environment",
            }
        ),
    )
    model = forms.ChoiceField(
        label="AI Model",
        choices=[
            ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash (Paid, Fast)"),
            ("anthropic/claude-sonnet-4", "Claude Sonnet 4 (Paid, Best)"),
            ("google/gemini-2.5-pro-preview-06-05", "Gemini 2.5 Pro (Paid, Premium)"),
        ],
        initial="google/gemini-2.0-flash-001",
        required=False,
        widget=forms.Select(attrs={"class": "input-dark"}),
    )

from django import forms

from .models import InventoryItem, Store


class BaseInventoryItemForm(forms.ModelForm):
    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household is not None:
            self.fields["store"].queryset = Store.objects.filter(household=household)
        else:
            self.fields["store"].queryset = Store.objects.none()

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")

        if quantity is not None and quantity < 0:
            raise forms.ValidationError("Quantity cannot be negative.")

        return quantity

    def clean_price(self):
        price = self.cleaned_data.get("price")

        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")

        return price


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
            "price",
            "store",
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
            "price": forms.NumberInput(
                attrs={
                    "class": "input input-bordered",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "store": forms.Select(attrs={"class": "select select-bordered"}),
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
    store = forms.ModelChoiceField(
        label="Receipt From (Optional)",
        queryset=Store.objects.none(),
        required=False,
        empty_label="Auto-detect from receipt",
        widget=forms.Select(attrs={"class": "input-dark"}),
        help_text="Override the AI-detected store; leave on auto-detect to trust the receipt.",
    )

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household is not None:
            self.fields["store"].queryset = Store.objects.filter(household=household)
        else:
            self.fields["store"].queryset = Store.objects.none()

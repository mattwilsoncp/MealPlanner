from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CustomUser


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    household_name = forms.CharField(
        max_length=100, required=False, help_text="Optional: give your household a name"
    )

    class Meta:
        model = CustomUser
        fields = ("email", "username", "password1", "password2", "household_name")

    def save(self, commit=True):
        from household.models import Household

        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        household_name = self.cleaned_data.get("household_name")
        if household_name:
            household = Household.objects.create(name=household_name)
        else:
            household = Household.objects.create(name="My Household")

        user.household = household

        if commit:
            user.save()

        return user

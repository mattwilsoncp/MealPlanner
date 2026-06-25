from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser


class LoginForm(AuthenticationForm):
    """Login form with optional household field — pick from existing or type a new one."""

    household = forms.CharField(max_length=100, required=False)

    def clean(self):
        cleaned_data = super().clean()
        household_name = cleaned_data.get("household")
        user = self.user_cache
        if household_name and user:
            from household.models import Household

            household, _ = Household.objects.get_or_create(name=household_name)
            user.household = household
            user.save(update_fields=["household"])
        return cleaned_data


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    household_name = forms.CharField(
        max_length=100, required=False, help_text="Optional: give your household a name"
    )

    class Meta:
        model = CustomUser
        fields = ("email", "username", "password1", "password2", "household_name")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def save(self, commit=True):
        from household.models import Household

        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        household_name = self.cleaned_data.get("household_name")
        if household_name:
            household, _ = Household.objects.get_or_create(name=household_name)
        else:
            household, _ = Household.objects.get_or_create(name="My Household")

        user.household = household

        if commit:
            user.save()

        return user

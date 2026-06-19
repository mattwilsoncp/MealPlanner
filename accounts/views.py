from django.contrib.auth import get_user_model, login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views import View
from django.views.generic import CreateView

from .forms import RegistrationForm

User = get_user_model()


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class DirectPasswordResetView(View):
    """Skip email — find user by email/username and redirect straight to reset form."""

    template_name = "registration/password_reset_form.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        identifier = request.POST.get("email", "").strip()
        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(username__iexact=identifier).first()
        )
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            return redirect("password_reset_confirm", uidb64=uid, token=token)
        # Don't reveal whether the account exists — show generic message
        messages.error(request, "No account found with that email or username.")
        return render(request, self.template_name)


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        from django.contrib.auth import login
        from django.contrib.auth.backends import ModelBackend

        response = super().form_valid(form)
        login(
            self.request,
            self.object,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        messages.success(self.request, "Welcome! Your account has been created.")
        return response

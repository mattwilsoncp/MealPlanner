from django.views.generic import TemplateView

from recipes.models import Recipe


class HomePageView(TemplateView):
    """Editorial landing page.

    Merges the original unauthenticated "Plan your meals" hero with the
    authenticated user's six-card index. The Recipe Reviews card surfaces
    a count of recipes that still need review so users see review-queue
    work-in-progress at a glance.
    """

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = getattr(user, "household", None) if user.is_authenticated else None
        if household is not None:
            context["reviews_count"] = Recipe.objects.filter(
                household=household,
                needs_review=True,
            ).count()
        return context

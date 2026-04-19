from django.db import models
from django.contrib.auth import get_user_model


class Rating(models.Model):
    """User rating for a recipe (1-5 scale)."""

    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    score = models.IntegerField(choices=RATING_CHOICES)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["recipe", "user"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipe.title}: {self.score}/5"

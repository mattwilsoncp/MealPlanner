from django.db import models
from django.urls import reverse
from household.models import Household


class Recipe(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="recipes"
    )
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="recipes/%Y/%m/%d/", blank=True, null=True)
    video_url = models.URLField(blank=True)
    transcript_log = models.CharField(
        max_length=512,
        blank=True,
        help_text="Path to the saved YouTube transcript log under logs/transcripts/, if any.",
    )
    on_hand_idea = models.BooleanField(default=False, db_index=True)
    leftover_worthy = models.BooleanField(default=False, db_index=True)
    needs_review = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["household", "created_at"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("recipes:recipe_detail", args=[self.pk])

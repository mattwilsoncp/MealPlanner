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


class RecipeWatchSession(models.Model):
    """Processing session that pairs a recipe's video with timestamped
    transcript segments and extracted frames.

    One session per recipe; re-processing a recipe replaces the prior
    segments and images.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        ERROR = "error", "Error"

    recipe = models.OneToOneField(
        Recipe,
        on_delete=models.CASCADE,
        related_name="watch_session",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Watch session for {self.recipe.title}"

    def get_absolute_url(self):
        return reverse("recipes:recipe_watch", args=[self.recipe.pk])


class RecipeWatchSegment(models.Model):
    """A single timestamped chunk of the video transcript plus the frame
    captured at its start time.
    """

    session = models.ForeignKey(
        RecipeWatchSession,
        on_delete=models.CASCADE,
        related_name="segments",
    )
    start_time = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text="Segment start time in seconds",
    )
    end_time = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text="Segment end time in seconds",
    )
    text = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="watch/%Y/%m/%d/",
        blank=True,
        null=True,
    )
    step_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Optional best-match recipe instruction step number",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"Segment {self.start_time}s-{self.end_time}s"

    @property
    def start_time_display(self):
        total = int(self.start_time)
        minutes, seconds = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

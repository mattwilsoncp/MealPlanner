from django.db import models


class Tag(models.Model):
    """Recipe tag, scoped to household."""

    household = models.ForeignKey(
        "household.Household", on_delete=models.CASCADE, related_name="tags"
    )
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6B7280")  # DaisyUI color hex

    class Meta:
        ordering = ["name"]
        unique_together = ["household", "name"]

    def __str__(self):
        return self.name


class RecipeTag(models.Model):
    """Many-to-many link between recipes and tags."""

    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["recipe", "tag"]

from django.db import models


class Instruction(models.Model):
    """Ordered instruction step for a recipe."""

    recipe = models.ForeignKey("recipes.Recipe", on_delete=models.CASCADE)
    step_number = models.PositiveIntegerField()
    text = models.TextField()
    image = models.ImageField(upload_to="instructions/%Y/%m/%d/", blank=True, null=True)

    class Meta:
        ordering = ["step_number"]

    def __str__(self):
        return f"Step {self.step_number}"

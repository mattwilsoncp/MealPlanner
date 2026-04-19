from django.core.validators import MinValueValidator
from django.db import models


class Household(models.Model):
    name = models.CharField(max_length=100, default="My Household")
    expiring_threshold_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Household"
        verbose_name_plural = "Households"

    def __str__(self):
        return self.name

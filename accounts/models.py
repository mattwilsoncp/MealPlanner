from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email or self.username

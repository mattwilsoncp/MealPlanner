from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from household.models import Household
from shopping.models import ShoppingListWeek


class ShoppingModelScaffoldTests(TestCase):
    def test_week_is_unique_per_household(self):
        household = Household.objects.create(name="Home")
        week_start = date(2026, 4, 13)

        ShoppingListWeek.objects.create(household=household, week_start=week_start)

        with self.assertRaises(IntegrityError):
            ShoppingListWeek.objects.create(household=household, week_start=week_start)

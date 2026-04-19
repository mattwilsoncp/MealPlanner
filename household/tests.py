from django.core.exceptions import ValidationError
from django.test import TestCase

from household.models import Household


class HouseholdModelTests(TestCase):
    def test_expiring_threshold_defaults_to_seven(self):
        household = Household(name="Test Household")

        self.assertEqual(household.expiring_threshold_days, 7)

    def test_expiring_threshold_requires_positive_value(self):
        household = Household(name="Test Household", expiring_threshold_days=0)

        with self.assertRaises(ValidationError):
            household.full_clean()

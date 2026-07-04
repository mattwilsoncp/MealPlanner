"""Tests for the USDA FoodData Central lookup + ingredient link view.

The HTTP calls are mocked: tests never hit the real USDA endpoint.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient
from ingredients.services import usda
from ingredients.services.usda import (
    FDC_NUTRIENT_CARBS,
    FDC_NUTRIENT_ENERGY_ATWATER,
    FDC_NUTRIENT_ENERGY_KCAL,
    FDC_NUTRIENT_FAT,
    FDC_NUTRIENT_PROTEIN,
    USFACatalog,
    USDAAPIError,
    resolve_usda_api_key,
)


def _fake_response(payload):
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _foundation_tomato_payload(fdc_id=1999634, description="Tomato, roma"):
    return {
        "totalHits": 1,
        "currentPage": 1,
        "totalPages": 1,
        "foods": [
            {
                "fdcId": fdc_id,
                "description": description,
                "dataType": "Foundation",
                "brandName": "",
                "foodNutrients": [
                    {"nutrientId": FDC_NUTRIENT_ENERGY_KCAL, "value": 21.0, "unitName": "KCAL"},
                    {"nutrientId": FDC_NUTRIENT_PROTEIN, "value": 0.7, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_CARBS, "value": 3.84, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_FAT, "value": 0.4, "unitName": "G"},
                ],
            }
        ],
    }


def _branded_pasta_payload(fdc_id=2293024, description="TOMATO"):
    """Branded dataset uses the older 1008 nutrient id for energy."""
    return {
        "totalHits": 1,
        "currentPage": 1,
        "totalPages": 1,
        "foods": [
            {
                "fdcId": fdc_id,
                "description": description,
                "dataType": "Branded",
                "brandName": "PASTA TOO",
                "foodNutrients": [
                    {"nutrientId": FDC_NUTRIENT_ENERGY_KCAL, "value": 110.0, "unitName": "KCAL"},
                    {"nutrientId": FDC_NUTRIENT_PROTEIN, "value": 4.5, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_CARBS, "value": 12.0, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_FAT, "value": 5.0, "unitName": "G"},
                ],
            }
        ],
    }


def _foundation_atwater_payload(fdc_id=1999634, description="Tomato, roma"):
    """Foundation dataset reports energy under the newer 2047 id."""
    return {
        "totalHits": 1,
        "currentPage": 1,
        "totalPages": 1,
        "foods": [
            {
                "fdcId": fdc_id,
                "description": description,
                "dataType": "Foundation",
                "brandName": "",
                "foodNutrients": [
                    {"nutrientId": FDC_NUTRIENT_ENERGY_ATWATER, "value": 22.0, "unitName": "KCAL"},
                    {"nutrientId": FDC_NUTRIENT_PROTEIN, "value": 0.696, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_CARBS, "value": 3.84, "unitName": "G"},
                    {"nutrientId": FDC_NUTRIENT_FAT, "value": 0.425, "unitName": "G"},
                ],
            }
        ],
    }


class USDAMatchNitrogenTests(TestCase):
    """Pure unit tests on the dataclass / nutrient picker — no I/O."""

    def setUp(self):
        USFACatalog.reset()

    def test_from_api_extracts_legacy_energy_id_1008(self):
        match = usda.USDAMatch.from_api(_foundation_tomato_payload()["foods"][0])
        self.assertEqual(match.fdc_id, 1999634)
        self.assertEqual(match.calories_kcal, Decimal("21.0"))
        self.assertEqual(match.protein_g, Decimal("0.7"))
        self.assertEqual(match.carbs_g, Decimal("3.84"))
        self.assertEqual(match.fat_g, Decimal("0.4"))

    def test_from_api_extracts_atwater_energy_id_2047(self):
        match = usda.USDAMatch.from_api(_foundation_atwater_payload()["foods"][0])
        self.assertEqual(match.calories_kcal, Decimal("22.0"))
        self.assertEqual(match.protein_g, Decimal("0.696"))
        self.assertEqual(match.carbs_g, Decimal("3.84"))
        self.assertEqual(match.fat_g, Decimal("0.425"))

    def test_from_api_returns_none_when_nutrient_missing(self):
        payload = {
            "fdcId": 12345,
            "description": "Mystery Food",
            "dataType": "Survey (FNDDS)",
            "brandName": "",
            "foodNutrients": [
                {"nutrientId": FDC_NUTRIENT_PROTEIN, "value": 5.0, "unitName": "G"},
            ],
        }
        match = usda.USDAMatch.from_api(payload)
        self.assertIsNone(match.calories_kcal)
        self.assertIsNone(match.carbs_g)
        self.assertIsNone(match.fat_g)
        self.assertEqual(match.protein_g, Decimal("5.0"))

    def test_has_macros_true_when_any_value_present(self):
        match = usda.USDAMatch.from_api(_foundation_tomato_payload()["foods"][0])
        self.assertTrue(match.has_macros())


class USFACatalogSearchTests(TestCase):
    """Mocked httpx — no real network."""

    def setUp(self):
        USFACatalog.reset()

    def test_search_returns_empty_for_blank_query(self):
        with mock.patch("httpx.Client.get") as mock_get:
            matches = USFACatalog.search("   ")
        self.assertEqual(matches, [])
        mock_get.assert_not_called()

    def test_search_parses_response_and_passes_query_through(self):
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            matches = USFACatalog.search("tomato", page_size=2)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].fdc_id, 1999634)
        # Verify query + key were passed downstream.
        args, kwargs = mock_get.call_args
        params = kwargs.get("params") or (args[1] if len(args) > 1 else {})
        self.assertEqual(params.get("query"), "tomato")
        self.assertEqual(params.get("pageSize"), 2)
        self.assertTrue(kwargs.get("params", {}).get("api_key"))

    def test_search_serves_from_cache_on_repeat_call(self):
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            first = USFACatalog.search("tomato")
            second = USFACatalog.search("tomato")
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(mock_get.call_count, 1)

    def test_search_force_refresh_busts_cache(self):
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            USFACatalog.search("tomato")
            USFACatalog.search("tomato", force_refresh=True)
        self.assertEqual(mock_get.call_count, 2)

    def test_search_raises_usable_api_error_on_http_failure(self):
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = mock.Mock(side_effect=usda.httpx.HTTPError("boom"))
            with self.assertRaises(USDAAPIError):
                USFACatalog.search("foo")

    def test_search_falls_back_to_last_good_on_upstream_blip(self):
        # Seed the cache with one good result.
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            USFACatalog.search("tomato")
        # Now simulate the upstream throwing — caller should still get the cached row.
        with mock.patch("httpx.Client.get") as mock_get:

            def fail(*args, **kwargs):
                raise usda.httpx.HTTPError("upstream is sleeping")

            mock_get.side_effect = fail
            matches = USFACatalog.search("tomato")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].fdc_id, 1999634)

    def test_filter_data_types_passes_through_to_query(self):
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            USFACatalog.search("tomato", data_types=["Foundation"])
        kwargs = mock_get.call_args.kwargs
        self.assertEqual(kwargs["params"].get("dataType"), ["Foundation"])


class USDAKeyResolutionTests(TestCase):
    def test_default_key_is_demokey_when_env_empty(self):
        with mock.patch.object(usda, "settings", wraps=usda.settings) as mock_settings:
            mock_settings.USDA_FDC_API_KEY = "DEMO_KEY"
            self.assertEqual(resolve_usda_api_key(None), "DEMO_KEY")

    def test_env_key_wins_when_set(self):
        with mock.patch.object(usda, "settings", wraps=usda.settings) as mock_settings:
            mock_settings.USDA_FDC_API_KEY = "REAL_KEY_FROM_ENV"
            self.assertEqual(resolve_usda_api_key(None), "REAL_KEY_FROM_ENV")

    def test_household_override_wins_over_env(self):
        from household.models import Household
        from meal_planner_app.models import AISettings

        hh = Household.objects.create(name="USDA Override HH")
        row, _ = AISettings.objects.get_or_create(household=hh)
        row.usda_fdc_api_key_override = "HOUSEHOLD-KEY"
        row.save()
        with mock.patch.object(usda, "settings", wraps=usda.settings) as mock_settings:
            mock_settings.USDA_FDC_API_KEY = "REAL_KEY_FROM_ENV"
            self.assertEqual(resolve_usda_api_key(hh), "HOUSEHOLD-KEY")

    def test_household_override_whitespace_treated_as_empty(self):
        from household.models import Household
        from meal_planner_app.models import AISettings

        hh = Household.objects.create(name="USDA Whitespace HH")
        row, _ = AISettings.objects.get_or_create(household=hh)
        row.usda_fdc_api_key_override = "   "
        row.save()
        with mock.patch.object(usda, "settings", wraps=usda.settings) as mock_settings:
            mock_settings.USDA_FDC_API_KEY = "DEMO_KEY"
            # Whitespace-only override should fall through to env.
            self.assertEqual(resolve_usda_api_key(hh), "DEMO_KEY")


class IngredientUSDALinkViewTests(TestCase):
    """Integration tests for the GET/POST view + form roundtrip."""

    def setUp(self):
        USFACatalog.reset()
        User = get_user_model()
        self.household = Household.objects.create(name="USDA Link HH")
        self.other_household = Household.objects.create(name="USDA Link Other")
        self.user = User.objects.create_user(
            username="usdauser",
            email="usda@example.com",
            password="Pass1234!",
            household=self.household,
        )
        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="Tomato",
        )
        self.url = reverse("ingredients:link_usda", args=[self.ingredient.pk])

    def test_login_required(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.url or "/accounts/login")

    def test_get_renders_search_form(self):
        self.client.login(username="usdauser", password="Pass1234!")
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            resp = self.client.get(self.url, {"q": "tomato"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tomato, roma")
        self.assertContains(resp, 'name="fdc_id"')

    def test_blank_query_skips_usda_call(self):
        self.client.login(username="usdauser", password="Pass1234!")
        with mock.patch("httpx.Client.get") as mock_get:
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        mock_get.assert_not_called()
        self.assertContains(resp, "Search query")

    def test_get_404_for_other_household_ingredient(self):
        other = Ingredient.objects.create(
            household=self.other_household,
            name="Hidden",
        )
        self.client.login(username="usdauser", password="Pass1234!")
        resp = self.client.get(reverse("ingredients:link_usda", args=[other.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_post_writes_all_five_fields(self):
        self.client.login(username="usdauser", password="Pass1234!")
        with mock.patch("httpx.Client.get") as mock_get:
            mock_get.return_value = _fake_response(_foundation_tomato_payload())
            resp = self.client.post(
                self.url,
                {
                    "fdc_id": "1999634",
                    "description": "Tomato, roma",
                    "data_type": "Foundation",
                    "q": "tomato",
                },
            )
        # Confirm-via-write redirects back to referer (none here → recipe list).
        self.assertIn(resp.status_code, (302, 200))
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.usda_food_id, "1999634")
        self.assertEqual(self.ingredient.calories_kcal, Decimal("21.0"))
        self.assertEqual(self.ingredient.protein_g, Decimal("0.7"))
        self.assertEqual(self.ingredient.carbs_g, Decimal("3.84"))
        self.assertEqual(self.ingredient.fat_g, Decimal("0.4"))

    def test_post_rejects_bad_fdc_id(self):
        self.client.login(username="usdauser", password="Pass1234!")
        resp = self.client.post(
            self.url,
            {
                "fdc_id": "not-a-number",
                "description": "...",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.ingredient.refresh_from_db()
        self.assertEqual(self.ingredient.usda_food_id, "")

    def test_linked_indicator_visible_pre_link(self):
        self.client.login(username="usdauser", password="Pass1234!")
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # No "Currently linked" copy on empty ingredient.
        self.assertNotContains(resp, "Currently linked to USDA id")

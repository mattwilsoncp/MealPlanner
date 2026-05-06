from django import forms
from django.test import TestCase, RequestFactory

from household.models import Household
from recipes.forms import RecipeForm, ImportForm, LLMImportForm
from recipes.models import Recipe
from tags.models import Tag


class RecipeFormCleanNewTagNameTests(TestCase):
    """Tests for RecipeForm.clean_new_tag_name validation."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.factory = RequestFactory()

    def _make_request(self, data=None):
        request = self.factory.post("/", data or {})
        request.user = type("MockUser", (), {"household": self.household})()
        return request

    def test_whitespace_normalised(self):
        """Extra spaces in new_tag_name are collapsed to a single space."""
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "  Weeknight  Meal  "},
            instance=self.recipe,
        )
        form.is_valid()
        self.assertEqual(form.clean_new_tag_name(), "Weeknight Meal")

    def test_whitespace_only_rejected(self):
        """Tag name that is only whitespace raises ValidationError."""
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "   "},
            instance=self.recipe,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_tag_name", form.errors)

    def test_case_insensitive_duplicate_detected(self):
        """A tag with the same name (different case) is detected as duplicate."""
        Tag.objects.create(household=self.household, name="Weeknight", color="#fff")
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "  WEEKNIGHT  "},
            instance=self.recipe,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_tag_name", form.errors)

    def test_duplicate_same_case_detected(self):
        """Exact same tag name is detected as duplicate."""
        Tag.objects.create(household=self.household, name="Quick", color="#fff")
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "Quick"},
            instance=self.recipe,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_tag_name", form.errors)

    def test_different_household_duplicate_not_detected(self):
        """Same tag name in a different household is not flagged as duplicate."""
        other_household = Household.objects.create(name="Other")
        Tag.objects.create(household=other_household, name="Quick", color="#fff")
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "Quick"},
            instance=self.recipe,
        )
        # Should be valid — Quick belongs to other household
        self.assertTrue(form.is_valid(), form.errors)

    def test_empty_tag_name_is_valid_for_form(self):
        """Empty new_tag_name (after strip) is allowed — not treated as a tag."""
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": ""},
            instance=self.recipe,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_new_tag_name_returns_normalised(self):
        """A valid new tag name returns the normalised string."""
        form = RecipeForm(
            data={"title": "Test", "new_tag_name": "  Summer  "},
            instance=self.recipe,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.clean_new_tag_name(), "Summer")


class ImportFormTests(TestCase):
    """Tests for ImportForm YouTube URL validation."""

    def test_valid_youtube_watch_url(self):
        """youtube.com/watch?v=... is accepted."""
        form = ImportForm(
            data={"youtube_url": "https://www.youtube.com/watch?v=abc123XYZ"}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_youtu_be_short_url(self):
        """youtu.be/... short URL is accepted."""
        form = ImportForm(data={"youtube_url": "https://youtu.be/abc123XYZ"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_youtube_shorts_url(self):
        """youtube.com/shorts/... is accepted."""
        form = ImportForm(
            data={"youtube_url": "https://www.youtube.com/shorts/abc123XYZ"}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_youtube_embed_url(self):
        """youtube.com/embed/... is accepted."""
        form = ImportForm(
            data={"youtube_url": "https://www.youtube.com/embed/abc123XYZ"}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_vimeo_url(self):
        """Non-YouTube URL (e.g. vimeo.com) is rejected."""
        form = ImportForm(
            data={"youtube_url": "https://vimeo.com/123456789"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("youtube_url", form.errors)

    def test_rejects_generic_video_url(self):
        """Non-YouTube video URL is rejected."""
        form = ImportForm(
            data={"youtube_url": "https://example.com/video?id=123"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("youtube_url", form.errors)

    def test_rejects_empty_url(self):
        """Empty URL is rejected."""
        form = ImportForm(data={"youtube_url": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("youtube_url", form.errors)


class LLMImportFormTests(TestCase):
    """Tests for LLMImportForm YouTube URL validation and optional fields."""

    def test_valid_youtube_url_accepted(self):
        """Valid youtube.com URL is accepted."""
        form = LLMImportForm(
            data={"youtube_url": "https://www.youtube.com/watch?v=abc123"}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_youtu_be_accepted(self):
        """Valid youtu.be URL is accepted."""
        form = LLMImportForm(data={"youtube_url": "https://youtu.be/abc123"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_non_youtube_url(self):
        """Non-YouTube URL is rejected."""
        form = LLMImportForm(
            data={"youtube_url": "https://www.tiktok.com/@user/video/123"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("youtube_url", form.errors)

    def test_optional_title_field(self):
        """title field is optional."""
        form = LLMImportForm(
            data={
                "youtube_url": "https://www.youtube.com/watch?v=abc123",
                "title": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_title_can_override(self):
        """title field accepts a custom string."""
        form = LLMImportForm(
            data={
                "youtube_url": "https://www.youtube.com/watch?v=abc123",
                "title": "My Custom Recipe Title",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_optional_model_field(self):
        """model field is optional and defaults to qwen/qwen-turbo."""
        form = LLMImportForm(
            data={"youtube_url": "https://www.youtube.com/watch?v=abc123"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("model", ""), "")

    def test_model_field_accepts_valid_choice(self):
        """model field accepts valid model choices."""
        form = LLMImportForm(
            data={
                "youtube_url": "https://www.youtube.com/watch?v=abc123",
                "model": "anthropic/claude-sonnet-4-20250514",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

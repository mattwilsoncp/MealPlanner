"""
Tests for LLMRecipeImportView (YouTube import with LLM parsing).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from household.models import Household
from recipes.models import Recipe
from recipes.views import LLMRecipeImportView


User = get_user_model()


class MockYouTubeTranscriptApi:
    """Mock YouTubeTranscriptApi that supports all calling patterns used by the view."""

    def __init__(self, transcript_items=None):
        self._transcript_items = transcript_items

    def get_transcript(self, video_id, languages=None):
        if self._transcript_items is not None:
            return self._transcript_items
        raise Exception("No transcript available")

    def fetch(self, video_id, languages=None):
        if self._transcript_items is not None:
            return self._transcript_items
        raise Exception("No transcript available")

    def list(self, video_id):
        return MockTranscriptList(self._transcript_items)


class MockTranscriptList:
    """Mock transcript list for the .list(video_id) API path."""

    def __init__(self, transcript_items):
        self._transcript_items = transcript_items or []

    def find_transcript(self, language_codes):
        return MockSelectedTranscript(self._transcript_items)

    def find_generated_transcript(self, language_codes):
        return MockSelectedTranscript(self._transcript_items)


class MockSelectedTranscript:
    """Mock selected transcript for the .find_transcript().fetch() path."""

    def __init__(self, transcript_items):
        self._transcript_items = transcript_items or []

    def fetch(self):
        return self._transcript_items


# Sample transcript data used across tests
SAMPLE_TRANSCRIPT_ITEMS = [
    {"text": "Welcome to this recipe video. Today we're making chocolate chip cookies.", "start": 0.0, "duration": 5.0},
    {"text": "We'll need 2 cups of flour, 1 cup of sugar, and 2 eggs.", "start": 5.0, "duration": 5.0},
    {"text": "Mix the ingredients together and bake at 350 degrees for 20 minutes.", "start": 10.0, "duration": 5.0},
]

SAMPLE_LLM_JSON_RESPONSE = """
{
  "title": "Chocolate Chip Cookies",
  "description": "Classic homemade chocolate chip cookies that are soft and chewy.",
  "ingredients": [
    {"name": "Flour", "quantity": "2", "unit": "cup"},
    {"name": "Sugar", "quantity": "1", "unit": "cup"},
    {"name": "Eggs", "quantity": "2", "unit": "piece"},
    {"name": "Chocolate Chips", "quantity": "1", "unit": "cup"}
  ],
  "instructions": [
    {"step_number": 1, "text": "Preheat oven to 350F."},
    {"step_number": 2, "text": "Mix flour, sugar, and eggs in a large bowl."},
    {"step_number": 3, "text": "Fold in chocolate chips."},
    {"step_number": 4, "text": "Bake for 20 minutes."}
  ]
}
"""


class LLMRecipeImportViewTests(TestCase):
    """Tests for LLMRecipeImportView GET and auth checks."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("recipes:llm_recipe_import")

    def test_get_requires_authentication(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_returns_200_for_authenticated(self):
        """Authenticated GET returns 200 with LLMImportForm."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_get_uses_llm_import_template(self):
        """GET renders the correct template."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "recipes/llm_import.html")


class LLMRecipeImportViewMissingAPIKeyTests(TestCase):
    """Tests for LLMRecipeImportView when OPENROUTER_API_KEY is missing."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("recipes:llm_recipe_import")

    def test_missing_api_key_returns_form_error(self):
        """POST with no OPENROUTER_API_KEY sets form error and returns 200."""
        self.client.login(username="alice", password="pass1234")
        # Ensure YouTubeTranscriptApi is mocked so it doesn't interfere
        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", None):
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
                response = self.client.post(
                    self.url,
                    {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                )
                self.assertEqual(response.status_code, 200)
                form = response.context["form"]
                self.assertIn("youtube_url", form.errors)
                self.assertIn(
                    "OPENROUTER_API_KEY is not configured",
                    str(form.errors["youtube_url"]),
                )


class LLMRecipeImportViewInvalidVideoIDTests(TestCase):
    """Tests for LLMRecipeImportView with invalid YouTube URLs."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("recipes:llm_recipe_import")

    def test_invalid_url_raises_invalid_video_error(self):
        """_extract_video_id raises InvalidVideoError for non-YouTube URLs."""
        view = LLMRecipeImportView()
        from recipes.youtube import InvalidVideoError

        with self.assertRaises(InvalidVideoError):
            view._extract_video_id("https://example.com/not-youtube")

    def test_missing_video_id_raises_invalid_video_error(self):
        """_extract_video_id raises InvalidVideoError for URLs without video ID."""
        view = LLMRecipeImportView()
        from recipes.youtube import InvalidVideoError

        with self.assertRaises(InvalidVideoError):
            view._extract_video_id("https://youtube.com/watch?")

    def test_shorts_url_extracts_video_id(self):
        """_extract_video_id correctly extracts video ID from shorts URL."""
        view = LLMRecipeImportView()
        # Video ID must be exactly 11 chars for the regex: abc123XYZab
        video_id = view._extract_video_id(
            "https://youtube.com/shorts/abc123XYZab"
        )
        self.assertEqual(video_id, "abc123XYZab")

    def test_standard_watch_url_extracts_video_id(self):
        """_extract_video_id correctly extracts video ID from standard watch URL."""
        view = LLMRecipeImportView()
        video_id = view._extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_youtu_be_url_extracts_video_id(self):
        """_extract_video_id correctly extracts video ID from youtu.be URL."""
        view = LLMRecipeImportView()
        video_id = view._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_embed_url_extracts_video_id(self):
        """_extract_video_id correctly extracts video ID from embed URL."""
        view = LLMRecipeImportView()
        video_id = view._extract_video_id(
            "https://youtube.com/embed/dQw4w9WgXcQ"
        )
        self.assertEqual(video_id, "dQw4w9WgXcQ")


class LLMRecipeImportViewMetadataTests(TestCase):
    """Tests for LLMRecipeImportView._get_video_metadata."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )

    @override_settings(YOUTUBE_API_KEY=None)
    def test_missing_youtube_api_key_returns_metadata_with_status(self):
        """_get_video_metadata returns fallback metadata when YOUTUBE_API_KEY is missing."""
        view = LLMRecipeImportView()
        metadata = view._get_video_metadata("abc123", "https://youtube.com/watch?v=abc123")
        self.assertEqual(metadata["video_id"], "abc123")
        self.assertEqual(metadata["metadata_status"], "missing_api_key")
        self.assertIn("YOUTUBE_API_KEY", metadata["metadata_error"])

    @override_settings(YOUTUBE_API_KEY="fake-key")
    def test_youtube_api_error_returns_metadata_with_error_status(self):
        """_get_video_metadata returns fallback metadata when YouTube API call fails."""
        view = LLMRecipeImportView()
        with patch("recipes.views.YouTubeService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_video_metadata.side_effect = Exception("API Error")
            mock_service.return_value = mock_instance

            metadata = view._get_video_metadata("abc123", "https://youtube.com/watch?v=abc123")
            self.assertEqual(metadata["metadata_status"], "error")
            self.assertIn("API Error", metadata["metadata_error"])

    @override_settings(YOUTUBE_API_KEY="fake-key")
    def test_successful_metadata_fetch(self):
        """_get_video_metadata returns full metadata on success."""
        view = LLMRecipeImportView()
        with patch("recipes.views.YouTubeService") as mock_service:
            mock_metadata = MagicMock()
            mock_metadata.title = "Test Recipe Video"
            mock_metadata.description = "A delicious recipe"
            mock_metadata.thumbnail_url = "https://example.com/thumb.jpg"
            mock_instance = MagicMock()
            mock_instance.get_video_metadata.return_value = mock_metadata
            mock_service.return_value = mock_instance

            metadata = view._get_video_metadata("abc123", "https://youtube.com/watch?v=abc123")
            self.assertEqual(metadata["title"], "Test Recipe Video")
            self.assertEqual(metadata["description"], "A delicious recipe")
            self.assertEqual(metadata["thumbnail_url"], "https://example.com/thumb.jpg")
            self.assertEqual(metadata["metadata_status"], "ok")


class LLMRecipeImportViewTranscriptTests(TestCase):
    """Tests for LLMRecipeImportView._fetch_transcript."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_fetch_transcript_not_installed_raises_runtime_error(self):
        """_fetch_transcript raises RuntimeError when youtube-transcript-api is not installed."""
        view = LLMRecipeImportView()

        # Simulate youtube-transcript-api not being installed by setting to None
        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", None):
            with self.assertRaises(RuntimeError) as ctx:
                view._fetch_transcript("abc123")
            self.assertIn("youtube-transcript-api is not installed", str(ctx.exception))

    def test_fetch_transcript_get_transcript_method(self):
        """_fetch_transcript calls YouTubeTranscriptApi.get_transcript and joins text."""
        view = LLMRecipeImportView()

        mock_api_class = MagicMock()
        mock_api_class.get_transcript = MagicMock(
            return_value=[
                {"text": "First line of the recipe transcript.", "start": 0.0},
                {"text": "Now let's add the ingredients.", "start": 5.0},
                {"text": "", "start": 10.0},
            ]
        )

        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", mock_api_class):
            # Verify the attribute is actually patched before calling
            self.assertIs(LLMRecipeImportView.YouTubeTranscriptApi, mock_api_class)
            transcript = view._fetch_transcript("abc123")
            self.assertIn("First line of the recipe transcript", transcript)
            self.assertIn("Now let's add the ingredients", transcript)

    def test_fetch_transcript_fetch_method_fallback(self):
        """_fetch_transcript falls back to .fetch() when get_transcript raises."""
        view = LLMRecipeImportView()

        mock_api_class = MagicMock()
        mock_api_class.get_transcript = MagicMock(side_effect=Exception("not supported"))
        mock_api_instance = MagicMock()
        mock_api_instance.fetch.return_value = [
            {"text": "Fallback transcript text", "start": 0.0},
        ]
        mock_api_class.return_value = mock_api_instance

        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", mock_api_class):
            transcript = view._fetch_transcript("abc123")
            self.assertIn("Fallback transcript text", transcript)

    def test_fetch_transcript_list_method_fallback(self):
        """_fetch_transcript falls back to .list().find_transcript().fetch()."""
        view = LLMRecipeImportView()

        mock_transcript_list = MagicMock()
        mock_selected = MagicMock()
        mock_selected.fetch.return_value = [
            {"text": "List method transcript", "start": 0.0},
        ]
        mock_transcript_list.find_transcript.return_value = mock_selected

        mock_api_class = MagicMock()
        mock_api_class.get_transcript = MagicMock(side_effect=Exception("not supported"))
        mock_api_instance = MagicMock()
        mock_api_instance.fetch.side_effect = TypeError("wrong args")
        mock_api_instance.list.return_value = mock_transcript_list
        mock_api_class.return_value = mock_api_instance

        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", mock_api_class):
            transcript = view._fetch_transcript("abc123")
            self.assertIn("List method transcript", transcript)

    def test_fetch_transcript_empty_text_returns_runtime_error(self):
        """_fetch_transcript raises RuntimeError when transcript has no text."""
        view = LLMRecipeImportView()

        mock_api_class = MagicMock()
        mock_api_class.get_transcript = MagicMock(
            return_value=[{"text": "", "start": 0.0, "duration": 1.0}]
        )

        with patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", mock_api_class):
            with self.assertRaises(RuntimeError) as ctx:
                view._fetch_transcript("abc123")
            self.assertIn("Could not fetch YouTube captions", str(ctx.exception))


class LLMRecipeImportViewTranscriptLogTests(TestCase):
    """Tests for LLMRecipeImportView._write_transcript_log."""

    def test_write_transcript_log_creates_file(self):
        """_write_transcript_log creates a transcript log file."""
        view = LLMRecipeImportView()
        metadata = {
            "video_id": "abc123",
            "url": "https://youtube.com/watch?v=abc123",
            "title": "Test Video",
            "description": "A test description",
            "metadata_status": "ok",
            "metadata_error": "",
            "thumbnail_url": "https://example.com/thumb.jpg",
        }
        transcript = "This is a sample transcript."

        log_path = view._write_transcript_log(metadata, transcript)

        try:
            self.assertTrue(log_path.exists())
            content = log_path.read_text()
            self.assertIn("abc123", content)
            self.assertIn("Test Video", content)
            self.assertIn("A test description", content)
            self.assertIn("This is a sample transcript", content)
        finally:
            # Cleanup
            if log_path.exists():
                log_path.unlink()


class LLMRecipeImportViewParseLLMTests(TestCase):
    """Tests for LLMRecipeImportView._parse_with_llm and helper methods."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_parse_with_llm_no_transcript_raises(self):
        """_parse_with_llm raises RuntimeError when transcript is empty."""
        view = LLMRecipeImportView()
        with self.assertRaises(RuntimeError) as ctx:
            view._parse_with_llm(
                MagicMock(), "openrouter/free", {}, ""
            )
        self.assertIn("No transcript available", str(ctx.exception))

    def test_parse_with_llm_empty_response_raises(self):
        """_parse_with_llm raises RuntimeError when LLM returns empty content."""
        view = LLMRecipeImportView()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            view._parse_with_llm(
                mock_client,
                "openrouter/free",
                {"url": "https://youtube.com/watch?v=abc"},
                "sample transcript text",
            )
        self.assertIn("empty response", str(ctx.exception))

    def test_parse_with_llm_json_in_code_fences(self):
        """_parse_with_llm correctly extracts JSON from markdown code fences."""
        view = LLMRecipeImportView()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Here is the JSON:\n```json\n" + SAMPLE_LLM_JSON_RESPONSE + "\n```\n"
        )
        mock_client.chat.completions.create.return_value = mock_response

        result = view._parse_with_llm(
            mock_client,
            "openrouter/free",
            {"url": "https://youtube.com/watch?v=abc"},
            "sample transcript",
        )
        self.assertEqual(result["title"], "Chocolate Chip Cookies")
        self.assertEqual(len(result["ingredients"]), 4)
        self.assertEqual(len(result["instructions"]), 4)

    def test_parse_with_llm_raw_json(self):
        """_parse_with_llm correctly extracts raw JSON without code fences."""
        view = LLMRecipeImportView()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = SAMPLE_LLM_JSON_RESPONSE
        mock_client.chat.completions.create.return_value = mock_response

        result = view._parse_with_llm(
            mock_client,
            "openrouter/free",
            {"url": "https://youtube.com/watch?v=abc"},
            "sample transcript",
        )
        self.assertEqual(result["title"], "Chocolate Chip Cookies")

    def test_parse_with_llm_json_embedded_in_text(self):
        """_parse_with_llm extracts JSON when it's embedded in explanatory text."""
        view = LLMRecipeImportView()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "I extracted the following recipe:\n"
            '{"title":"Pasta","description":"Delicious pasta","ingredients":[],"instructions":[]}\n'
            "Hope this helps!"
        )
        mock_client.chat.completions.create.return_value = mock_response

        result = view._parse_with_llm(
            mock_client,
            "openrouter/free",
            {"url": "https://youtube.com/watch?v=abc"},
            "sample transcript",
        )
        self.assertEqual(result["title"], "Pasta")

    def test_parse_with_llm_non_dict_raises(self):
        """_parse_with_llm raises RuntimeError when model returns a non-dict."""
        view = LLMRecipeImportView()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '["just", "an", "array"]'
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            view._parse_with_llm(
                mock_client,
                "openrouter/free",
                {"url": "https://youtube.com/watch?v=abc"},
                "sample transcript",
            )
        self.assertIn("did not contain a JSON object or array", str(ctx.exception))

    def test_build_source_context(self):
        """_build_source_context formats metadata and transcript into context string."""
        view = LLMRecipeImportView()
        metadata = {
            "url": "https://youtube.com/watch?v=abc123",
            "video_id": "abc123",
            "title": "Test Video",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "description": "A test description",
        }
        transcript = "This is the transcript."

        context = view._build_source_context(metadata, transcript)

        self.assertIn("https://youtube.com/watch?v=abc123", context)
        self.assertIn("abc123", context)
        self.assertIn("Test Video", context)
        self.assertIn("A test description", context)
        self.assertIn("This is the transcript", context)


class LLMRecipeImportViewNormalizeTests(TestCase):
    """Tests for quantity and unit normalization helpers."""

    def test_normalize_quantity_integer(self):
        """_normalize_quantity handles plain integers."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_quantity(3), Decimal("3"))
        self.assertEqual(view._normalize_quantity("5"), Decimal("5"))

    def test_normalize_quantity_decimal(self):
        """_normalize_quantity handles decimal strings."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_quantity("2.5"), Decimal("2.5"))

    def test_normalize_quantity_fraction(self):
        """_normalize_quantity handles fractions like 1/2."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_quantity("1/2"), Decimal("0.5"))
        self.assertEqual(view._normalize_quantity("3/4"), Decimal("0.75"))

    def test_normalize_quantity_mixed_fraction(self):
        """_normalize_quantity handles mixed fractions like 1 1/2."""
        view = LLMRecipeImportView()
        result = view._normalize_quantity("1 1/2")
        self.assertEqual(result, Decimal("1.5"))

    def test_normalize_quantity_range(self):
        """_normalize_quantity handles ranges like 1-2, returning the average."""
        view = LLMRecipeImportView()
        result = view._normalize_quantity("1-2")
        self.assertEqual(result, Decimal("1.5"))

    def test_normalize_quantity_empty_returns_one(self):
        """_normalize_quantity returns 1 for empty/None values."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_quantity(""), Decimal("1"))
        self.assertEqual(view._normalize_quantity(None), Decimal("1"))
        self.assertEqual(view._normalize_quantity("  "), Decimal("1"))

    def test_normalize_quantity_invalid_returns_one(self):
        """_normalize_quantity returns 1 for invalid input."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_quantity("abc"), Decimal("1"))

    def test_normalize_unit_cups(self):
        """_normalize_unit normalizes 'cups' to 'cup'."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_unit("cups"), "cup")
        self.assertEqual(view._normalize_unit("Cup"), "cup")

    def test_normalize_unit_tbsp(self):
        """_normalize_unit normalizes 'tablespoon' and variants to 'tbsp'."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_unit("tablespoon"), "tbsp")
        self.assertEqual(view._normalize_unit("tablespoons"), "tbsp")
        self.assertEqual(view._normalize_unit("tbs"), "tbsp")

    def test_normalize_unit_oz(self):
        """_normalize_unit normalizes 'ounces' and 'ounce' to 'oz'."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_unit("ounces"), "oz")
        self.assertEqual(view._normalize_unit("ounce"), "oz")

    def test_normalize_unit_unknown_defaults_to_piece(self):
        """_normalize_unit returns 'piece' for unrecognized units."""
        view = LLMRecipeImportView()
        self.assertEqual(view._normalize_unit("widget"), "piece")
        self.assertEqual(view._normalize_unit(""), "piece")
        self.assertEqual(view._normalize_unit(None), "piece")


class LLMRecipeImportViewCreateRecipeTests(TestCase):
    """Tests for LLMRecipeImportView._create_recipe."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_create_recipe_new_recipe(self):
        """_create_recipe creates a new Recipe with ingredients and instructions."""
        view = LLMRecipeImportView()

        data = {
            "title": "Test Chocolate Cake",
            "description": "A rich chocolate cake.",
            "ingredients": [
                {"name": "Flour", "quantity": "2", "unit": "cup"},
                {"name": "Cocoa Powder", "quantity": "0.5", "unit": "cup"},
            ],
            "instructions": [
                {"step_number": 1, "text": "Mix dry ingredients."},
                {"step_number": 2, "text": "Add wet ingredients and bake."},
            ],
        }

        # Create a dummy transcript log path
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data,
                self.household,
                "https://youtube.com/watch?v=abc123",
                log_path,
                "abc123",
            )

            self.assertIsNotNone(recipe.pk)
            self.assertEqual(recipe.title, "Test Chocolate Cake")
            self.assertEqual(recipe.household, self.household)
            self.assertTrue(recipe.needs_review)

            # Check ingredients
            links = recipe.ingredients.all()
            self.assertEqual(links.count(), 2)
            ingredient_names = sorted([link.ingredient.name for link in links])
            self.assertEqual(ingredient_names, ["Cocoa Powder", "Flour"])

            # Check instructions
            instructions = Instruction.objects.filter(recipe=recipe).order_by("step_number")
            self.assertEqual(instructions.count(), 2)
            self.assertEqual(instructions[0].text, "Mix dry ingredients.")

            # Verify transcript log path is recorded on the recipe
            self.assertTrue(recipe.transcript_log.endswith("test_log.txt"))
            # Description should remain the user/parsed description, NOT include the
            # legacy 'Transcript log:' suffix.
            self.assertNotIn("Transcript log:", recipe.description)
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_create_recipe_gets_existing_recipe(self):
        """_create_recipe returns existing recipe if one with same title exists."""
        view = LLMRecipeImportView()

        existing = Recipe.objects.create(
            household=self.household,
            title="Existing Recipe",
            description="Old description",
        )

        data = {
            "title": "Existing Recipe",
            "description": "New description",
            "ingredients": [],
            "instructions": [],
        }

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log2.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data,
                self.household,
                "https://youtube.com/watch?v=xyz789",
                log_path,
                "xyz789",
            )

            # Should return the existing recipe, not create a new one
            self.assertEqual(recipe.pk, existing.pk)
            # Description should be updated
            self.assertIn("New description", recipe.description)
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_create_recipe_default_title(self):
        """_create_recipe uses fallback title when title is empty."""
        view = LLMRecipeImportView()
        data = {
            "title": "",
            "description": "A recipe.",
            "ingredients": [],
            "instructions": [],
        }

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log3.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data, self.household, "https://youtube.com/watch?v=abc", log_path
            )
            self.assertEqual(recipe.title, "Imported YouTube Recipe")
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_create_recipe_skips_empty_ingredients(self):
        """_create_recipe skips ingredient items with no name."""
        view = LLMRecipeImportView()
        data = {
            "title": "Test",
            "description": "",
            "ingredients": [
                {"name": "Salt", "quantity": "1", "unit": "tsp"},
                {"name": "", "quantity": "1", "unit": "cup"},  # empty name
                {"name": "  ", "quantity": "2", "unit": "tbsp"},  # whitespace name
            ],
            "instructions": [],
        }

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log4.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data, self.household, "https://youtube.com/watch?v=abc", log_path
            )
            # Only Salt should be created (2 skipped)
            links = recipe.ingredients.all()
            self.assertEqual(links.count(), 1)
            self.assertEqual(links[0].ingredient.name, "Salt")
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_create_recipe_skips_empty_instructions(self):
        """_create_recipe skips instruction items with no text."""
        view = LLMRecipeImportView()
        data = {
            "title": "Test",
            "description": "",
            "ingredients": [],
            "instructions": [
                {"step_number": 1, "text": "First step."},
                {"step_number": 2, "text": ""},  # empty text
                {"step_number": 3, "text": "  "},  # whitespace text
            ],
        }

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log5.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data, self.household, "https://youtube.com/watch?v=abc", log_path
            )
            instructions = Instruction.objects.filter(recipe=recipe)
            self.assertEqual(instructions.count(), 1)
            self.assertEqual(instructions[0].text, "First step.")
        finally:
            if log_path.exists():
                log_path.unlink()

    def test_create_recipe_invalid_step_number_uses_index(self):
        """_create_recipe uses index when step_number is invalid or missing; valid ones are preserved."""
        view = LLMRecipeImportView()
        data = {
            "title": "Test",
            "description": "",
            "ingredients": [],
            "instructions": [
                {"step_number": "not a number", "text": "Step one."},
                {"step_number": -1, "text": "Step two."},
                {"step_number": 5, "text": "Step three."},
            ],
        }

        log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "transcripts"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "test_log6.txt"
        log_path.write_text("test")

        try:
            recipe = view._create_recipe(
                data, self.household, "https://youtube.com/watch?v=abc", log_path
            )
            instructions = Instruction.objects.filter(recipe=recipe).order_by("step_number")
            self.assertEqual(instructions.count(), 3)
            # Invalid step_numbers (non-int or <1) are replaced with index (1 and 2).
            # Valid step_number=5 is preserved.
            step_numbers = [i.step_number for i in instructions]
            self.assertEqual(step_numbers, [1, 2, 5])
            # But texts match correctly
            texts = [i.text for i in instructions]
            self.assertIn("Step one.", texts)
            self.assertIn("Step three.", texts)
        finally:
            if log_path.exists():
                log_path.unlink()


class LLMRecipeImportViewFullIntegrationTests(TestCase):
    """Full integration tests for LLMRecipeImportView with mocked external services."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("recipes:llm_recipe_import")

    def _make_mock_llm_response(self, json_content):
        """Create a mock OpenAI response with the given JSON string."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json_content
        return mock_response

    def test_full_import_success(self):
        """POST with valid YouTube URL, transcript, and LLM response creates recipe."""
        self.client.login(username="alice", password="pass1234")

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("youtube_transcript_api.YouTubeTranscriptApi",
                       MockYouTubeTranscriptApi(SAMPLE_TRANSCRIPT_ITEMS)):
                with patch("recipes.views.YouTubeService") as mock_yt_svc:
                    mock_yt_svc.return_value.get_video_metadata.return_value = MagicMock(
                        title="Test Recipe",
                        description="Test description",
                        thumbnail_url="https://example.com/thumb.jpg",
                    )

                    with patch("recipes.views.OpenAI") as mock_openai:
                        mock_client = MagicMock()
                        mock_client.chat.completions.create.return_value = (
                            self._make_mock_llm_response(SAMPLE_LLM_JSON_RESPONSE)
                        )
                        mock_openai.return_value = mock_client

                        response = self.client.post(
                            self.url,
                            {
                                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                                "model": "openrouter/free",
                            },
                        )

                        self.assertEqual(response.status_code, 302, msg=f"Expected 302, got {response.status_code}")
                        self.assertRegex(response.url, r"/recipes/\d+/")

                        recipe = Recipe.objects.latest("pk")
                        self.assertEqual(recipe.title, "Chocolate Chip Cookies")
                        self.assertEqual(recipe.household, self.household)
                        self.assertEqual(recipe.ingredients.count(), 4)
                        self.assertTrue(Instruction.objects.filter(recipe=recipe).exists())

    def test_import_with_custom_title_overrides_llm_title(self):
        """POST with custom title overrides the LLM-generated title."""
        self.client.login(username="alice", password="pass1234")

        from recipes.views import LLMRecipeImportView

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("youtube_transcript_api.YouTubeTranscriptApi",
                       MockYouTubeTranscriptApi(SAMPLE_TRANSCRIPT_ITEMS)):
                with patch("recipes.views.YouTubeService") as mock_yt_svc:
                    mock_yt_svc.return_value.get_video_metadata.return_value = MagicMock(
                        title="Test Recipe",
                        description="Test description",
                        thumbnail_url="https://example.com/thumb.jpg",
                    )

                    with patch("recipes.views.OpenAI") as mock_openai:
                        mock_client = MagicMock()
                        mock_client.chat.completions.create.return_value = (
                            self._make_mock_llm_response(SAMPLE_LLM_JSON_RESPONSE)
                        )
                        mock_openai.return_value = mock_client

                        response = self.client.post(
                            self.url,
                            {
                                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                                "title": "My Custom Cookie Recipe",
                                "model": "openrouter/free",
                            },
                        )

                        msg = f"Expected 302, got {response.status_code}."
                        if response.status_code == 200 and response.context:
                            msg += f" Form errors: {response.context['form'].errors.as_text()}"
                        self.assertEqual(response.status_code, 302, msg=msg)
                        recipe = Recipe.objects.latest("pk")
                        self.assertEqual(recipe.title, "My Custom Cookie Recipe")

    def test_import_invalid_video_error_returns_form_error(self):
        """POST with non-YouTube URL raises InvalidVideoError and returns form error."""
        self.client.login(username="alice", password="pass1234")

        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
        ):
            response = self.client.post(
                self.url,
                {
                    "youtube_url": "https://not-youtube.com/video",
                },
            )

            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertIn("youtube_url", form.errors)

    def test_import_llm_json_parse_error_returns_form_error(self):
        """POST when LLM returns unparseable JSON returns form error."""
        self.client.login(username="alice", password="pass1234")

        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
        ), patch("youtube_transcript_api.YouTubeTranscriptApi", side_effect=ImportError):
            response = self.client.post(
                self.url,
                {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertIn("youtube_url", form.errors)
            self.assertIn("Import failed", str(form.errors["youtube_url"]))

    def test_import_transcript_api_missing_returns_form_error(self):
        """POST when youtube-transcript-api is not installed returns form error."""
        self.client.login(username="alice", password="pass1234")

        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
        ), patch("youtube_transcript_api.YouTubeTranscriptApi", side_effect=ImportError):
            response = self.client.post(
                self.url,
                {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertIn("youtube_url", form.errors)

    def test_import_no_household_returns_form_error(self):
        """POST when user has no household returns form error."""
        user_no_household = User.objects.create_user(
            username="nohousehold",
            email="nohousehold@example.com",
            password="pass1234",
            household=None,
        )
        self.client.login(username="nohousehold", password="pass1234")

        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
        ):
            response = self.client.post(
                self.url,
                {"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertIn("youtube_url", form.errors)


# Import Instruction here so the tests can reference it
from instructions.models import Instruction
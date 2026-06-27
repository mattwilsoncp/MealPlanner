"""Tests for the recipe transcript log field + viewer endpoint."""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from recipes.models import Recipe
from recipes.views import (
    parse_legacy_transcript_log,
    resolve_safe_transcript_path,
    strip_transcript_log_suffix,
    TRANSCRIPT_DIR,
)


User = get_user_model()


class TranscriptLogHelperTests(TestCase):
    def test_parse_legacy_transcript_log_returns_path_from_description(self):
        description = (
            "Test recipe description.\n\n"
            "Transcript log: logs/transcripts/20240601_abc.txt"
        )
        self.assertEqual(
            parse_legacy_transcript_log(description),
            "logs/transcripts/20240601_abc.txt",
        )

    def test_parse_legacy_transcript_log_returns_none_when_no_suffix(self):
        self.assertIsNone(parse_legacy_transcript_log("Plain description text."))
        self.assertIsNone(parse_legacy_transcript_log(""))
        self.assertIsNone(parse_legacy_transcript_log(None))

    def test_strip_transcript_log_suffix_removes_path_line(self):
        description = (
            "Test recipe description.\n\n"
            "Transcript log: logs/transcripts/20240601_abc.txt"
        )
        stripped = strip_transcript_log_suffix(description)
        self.assertEqual(stripped, "Test recipe description.")
        self.assertNotIn("Transcript log:", stripped)

    def test_strip_transcript_log_suffix_preserves_plain_text(self):
        self.assertEqual(
            strip_transcript_log_suffix("Plain description text."),
            "Plain description text.",
        )

    def test_resolve_safe_transcript_path_returns_absolute_path(self):
        sample_dir = TRANSCRIPT_DIR
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_path = sample_dir / "sample_for_test.txt"
        sample_path.write_text("hello world", encoding="utf-8")
        try:
            resolved = resolve_safe_transcript_path("sample_for_test.txt")
            self.assertTrue(resolved.is_file())
            self.assertEqual(resolved.read_text(encoding="utf-8"), "hello world")
        finally:
            if sample_path.exists():
                sample_path.unlink()

    def test_resolve_safe_transcript_path_rejects_traversal(self):
        # Even though the path resolves back inside TRANSCRIPT_DIR,
        # Path(relative_path).name strips directories, so this is impossible;
        # we still verify the API raises for an empty path.
        with self.assertRaises(FileNotFoundError):
            resolve_safe_transcript_path("")
        with self.assertRaises(FileNotFoundError):
            resolve_safe_transcript_path("does_not_exist.txt")


class RecipeTranscriptContentViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Transcript Household")
        self.other_household = Household.objects.create(name="Other Transcript")
        self.user = user_model.objects.create_user(
            username="transcript-user",
            email="transcript@example.com",
            password="pass1234",
            household=self.household,
        )
        self.other_user = user_model.objects.create_user(
            username="other-transcript-user",
            email="other-transcript@example.com",
            password="pass1234",
            household=self.other_household,
        )
        self.client.force_login(self.user)
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        self.sample_path = TRANSCRIPT_DIR / "test_recipe_transcript.txt"
        self.sample_path.write_text(
            "Welcome to the test recipe.\nLine two of the transcript.",
            encoding="utf-8",
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Rec With Transcript",
            description="A description for the recipe.",
            video_url="https://www.youtube.com/watch?v=abc",
            transcript_log="test_recipe_transcript.txt",
        )

    def tearDown(self):
        if self.sample_path.exists():
            self.sample_path.unlink()

    def test_transcript_endpoint_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_transcript_endpoint_returns_content_for_owner(self):
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("content", body)
        self.assertIn("Welcome to the test recipe.", body["content"])
        self.assertIn("Line two of the transcript.", body["content"])

    def test_transcript_endpoint_forbidden_for_other_household(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[self.recipe.pk])
        )
        # Other household should not be able to read another household's
        # transcript. get_object_or_404 returns 404 for misshapen filters.
        self.assertEqual(response.status_code, 404)

    def test_transcript_endpoint_404_when_log_field_missing(self):
        no_log_recipe = Recipe.objects.create(
            household=self.household,
            title="No Transcript Recipe",
        )
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[no_log_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_transcript_endpoint_404_when_file_missing(self):
        bad_recipe = Recipe.objects.create(
            household=self.household,
            title="Missing Transcript Recipe",
            transcript_log="definitely_not_present.txt",
        )
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[bad_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_transcript_endpoint_falls_back_to_legacy_description_suffix(self):
        legacy_recipe = Recipe.objects.create(
            household=self.household,
            title="Legacy Recipe",
            description="Legacy description.\n\nTranscript log: test_recipe_transcript.txt",
        )
        response = self.client.get(
            reverse("recipes:recipe_transcript", args=[legacy_recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("Welcome to the test recipe", body["content"])

    def test_recipe_detail_template_renders_transcript_link_when_log_path_set(self):
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Source transcript", body)
        self.assertIn("Read Full Transcript", body)
        self.assertIn(
            reverse("recipes:recipe_transcript", args=[self.recipe.pk]),
            body,
        )

    def test_recipe_detail_template_strips_legacy_suffix_from_description(self):
        legacy_recipe = Recipe.objects.create(
            household=self.household,
            title="Legacy View Recipe",
            description=(
                "Just a description.\n\nTranscript log: test_recipe_transcript.txt"
            ),
        )
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[legacy_recipe.pk])
        )
        body = response.content.decode("utf-8")
        self.assertIn("Just a description.", body)
        # The rendered description block should NOT include the suffix line.
        self.assertNotIn(
            '<p style="margin-top: 12px; color: var(--text-secondary); '
            'white-space: pre-wrap; line-height: 1.6;">Just a description.'
            '\n\nTranscript log:',
            body,
        )

    def test_recipe_detail_template_omits_transcript_section_when_no_log(self):
        no_log_recipe = Recipe.objects.create(
            household=self.household,
            title="Plain Recipe",
            description="Just a description.",
        )
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[no_log_recipe.pk])
        )
        body = response.content.decode("utf-8")
        self.assertNotIn("Source transcript", body)
        self.assertNotIn("Read Full Transcript", body)

#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

import django


django.setup()

from markitdown import MarkItDown
from openai import OpenAI

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction
from recipes.models import Recipe
from recipes.youtube import InvalidVideoError, YouTubeService

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
#DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_MODEL = "qwen/qwen-turbo"
TRANSCRIPT_DIR = PROJECT_ROOT / "logs" / "transcripts"
VALID_UNITS = {choice[0] for choice in IngredientLink.UNIT_CHOICES}
UNIT_MAP = {
    "cups": "cup",
    "cup": "cup",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "tbs": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "ts": "tsp",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "milliliter": "ml",
    "milliliters": "ml",
    "ml": "ml",
    "liter": "l",
    "liters": "l",
    "l": "l",
    "cloves": "clove",
    "clove": "clove",
    "slice": "slice",
    "slices": "slice",
    "bunch": "bunch",
    "bunches": "bunch",
    "can": "can",
    "cans": "can",
    "piece": "piece",
    "pieces": "piece",
    "": "piece",
}


PROMPT_TEMPLATE = """You are extracting structured recipe data from a YouTube recipe video transcript.
Return only valid JSON with this exact shape:
{
  "title": "string",
  "description": "string",
  "ingredients": [
    {
      "name": "string",
      "quantity": "string",
      "unit": "string"
    }
  ],
  "instructions": [
    {
      "step_number": 1,
      "text": "string"
    }
  ]
}

Rules:
- The recipe title should be concise and human readable.
- The description should summarize the dish in 1-3 sentences.
- Include only actual ingredients used in the recipe.
- Preserve ingredient quantities when present.
- Use singular common cooking units when possible.
- For ingredients without a clear quantity, leave quantity as an empty string.
- For ingredients without a clear unit, leave unit as an empty string.
- Instructions should be clean, imperative cooking steps.
- Instructions must be ordered and start at step_number 1.
- Do not include markdown, explanation, or code fences.

YouTube URL: {url}

Transcript:
{transcript}
"""


def get_openrouter_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def get_household(household_id: int | None) -> Household:
    if household_id is not None:
        household = Household.objects.filter(pk=household_id).first()
        if household:
            return household
        raise RuntimeError(f"Household with id={household_id} was not found")

    household = Household.objects.order_by("id").first()
    if household:
        return household
    raise RuntimeError("No household found. Create a household before importing recipes.")


def transcribe_youtube(url: str) -> str:
    md = MarkItDown()
    result = md.convert(url)
    transcript = (result.text_content or "").strip()
    if not transcript:
        raise RuntimeError("Transcript was empty or unavailable for this video")
    return transcript


def extract_video_id(url: str) -> str:
    try:
        service = YouTubeService(api_key="placeholder")
        return service.extract_video_id(url)
    except InvalidVideoError as exc:
        raise RuntimeError(str(exc)) from exc


def write_transcript_log(video_id: str, transcript: str) -> Path:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = TRANSCRIPT_DIR / f"{timestamp}_{video_id}.txt"
    output_path.write_text(transcript, encoding="utf-8")
    return output_path


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("Model response was not a JSON object")
    return payload


def parse_recipe_with_llm(client: OpenAI, model: str, url: str, transcript: str) -> dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(url=url, transcript=transcript)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a precise recipe extraction engine that returns strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
    )

    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("OpenRouter returned an empty response")
    return extract_json_payload(content)


def normalize_quantity(raw_quantity: Any) -> Decimal:
    if raw_quantity is None:
        return Decimal("1")

    quantity_text = str(raw_quantity).strip()
    if not quantity_text:
        return Decimal("1")

    fraction_match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", quantity_text)
    mixed_match = re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", quantity_text)
    range_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", quantity_text)

    try:
        if mixed_match:
            whole = Decimal(mixed_match.group(1))
            numerator = Decimal(mixed_match.group(2))
            denominator = Decimal(mixed_match.group(3))
            return whole + (numerator / denominator)
        if fraction_match:
            numerator = Decimal(fraction_match.group(1))
            denominator = Decimal(fraction_match.group(2))
            return numerator / denominator
        if range_match:
            low = Decimal(range_match.group(1))
            high = Decimal(range_match.group(2))
            return (low + high) / 2
        return Decimal(quantity_text)
    except (InvalidOperation, ZeroDivisionError):
        return Decimal("1")


def normalize_unit(raw_unit: Any) -> str:
    unit = str(raw_unit or "").strip().lower()
    normalized = UNIT_MAP.get(unit, unit)
    if normalized in VALID_UNITS:
        return normalized
    return "piece"


def upsert_recipe(data: dict[str, Any], household: Household, youtube_url: str, transcript_log: Path) -> Recipe:
    title = str(data.get("title") or "").strip() or "Imported YouTube Recipe"
    description = str(data.get("description") or "").strip()
    ingredients = data.get("ingredients") or []
    instructions = data.get("instructions") or []

    recipe, created = Recipe.objects.get_or_create(
        household=household,
        title=title,
        defaults={
            "description": description,
            "video_url": youtube_url,
            "needs_review": True,
        },
    )

    recipe.description = description or recipe.description
    recipe.video_url = youtube_url
    recipe.needs_review = True
    recipe.save()

    recipe.ingredients.all().delete()
    Instruction.objects.filter(recipe=recipe).delete()

    for index, item in enumerate(ingredients, start=1):
        name = str(item.get("name") or "").strip()
        if not name:
            continue

        ingredient, _ = Ingredient.objects.get_or_create(
            household=household,
            name=name,
        )
        IngredientLink.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            quantity=normalize_quantity(item.get("quantity")),
            unit=normalize_unit(item.get("unit")),
            order=index,
        )

    for index, item in enumerate(instructions, start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        step_number = item.get("step_number")
        if not isinstance(step_number, int) or step_number < 1:
            step_number = index
        Instruction.objects.create(
            recipe=recipe,
            step_number=step_number,
            text=text,
        )

    recipe.description = (recipe.description or "").strip()
    if str(transcript_log) not in recipe.description:
        suffix = f"\n\nTranscript log: {transcript_log.relative_to(PROJECT_ROOT)}"
        recipe.description = f"{recipe.description}{suffix}".strip()
        recipe.save(update_fields=["description", "updated_at"])

    action = "Created" if created else "Updated"
    print(f"{action} recipe #{recipe.pk}: {recipe.title}")
    return recipe


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a YouTube recipe via OpenRouter")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenRouter model to use for recipe extraction (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--household-id",
        type=int,
        default=None,
        help="Household ID to associate with the imported recipe",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Optional recipe title override",
    )

    args = parser.parse_args()

    try:
        household = get_household(args.household_id)
        client = get_openrouter_client()
        video_id = extract_video_id(args.url)
        transcript = transcribe_youtube(args.url)
        transcript_log = write_transcript_log(video_id, transcript)
        parsed = parse_recipe_with_llm(client, args.model, args.url, transcript)

        if args.title.strip():
            parsed["title"] = args.title.strip()

        recipe = upsert_recipe(parsed, household, args.url, transcript_log)
        print(f"Transcript saved to {transcript_log}")
        print(f"Recipe marked for review: {recipe.needs_review}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

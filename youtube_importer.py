#!/usr/bin/env python3
"""
Simple YouTube Recipe Importer - Call from Python

Usage:
    from youtube_importer import import_recipe

    result = import_recipe("https://www.youtube.com/watch?v=VIDEO_ID")
    print(result)
"""

import os
import sys
import re

# Add project to path and setup Django
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

import django

django.setup()

from recipes.models import Recipe
from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction
from household.models import Household


UNIT_MAP = {
    "cup": "cups",
    "tbsp": "tablespoons",
    "tsp": "teaspoons",
    "oz": "ounces",
    "lb": "pounds",
    "tbs": "tablespoons",
    "ts": "teaspoons",
}


def get_api_key():
    """Get YouTube API key from settings or env."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if key:
        return key
    try:
        from meal_planner import settings

        return getattr(settings, "YOUTUBE_API_KEY", "")
    except Exception:
        return ""


def get_household(user=None):
    """Get household for user or first available."""
    if user and hasattr(user, "household") and user.household:
        return user.household
    return Household.objects.first()


def parse_ingredients(text):
    """Parse ingredients from text."""
    ingredients = []
    lines = text.split("\n")
    in_section = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Section detection
        if re.match(
            r"^(?:ingredients|directions?|you[' ]?ll need)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = True
            continue
        if re.match(
            r"^(?:instructions?|directions?|steps?|method)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = False
            continue

        if in_section or line.startswith(("-", "*", "•")):
            clean = line.lstrip("-*• ").strip()
            # Parse quantity
            m = re.match(
                r"^(\d+(?:[\d\/\.]+)?(?:\s*-\s*\d+)?)\s*([a-zA-Z]+)?\s*(.+)", clean
            )
            if m:
                qty, unit, name = m.group(1) or "", m.group(2) or "", m.group(3)
                ingredients.append(
                    {
                        "name": name,
                        "quantity": qty,
                        "unit": UNIT_MAP.get(unit.lower(), unit.lower())
                        if unit
                        else "piece",
                    }
                )
            else:
                ingredients.append({"name": clean, "quantity": "1", "unit": "piece"})

    return ingredients[:30]


def parse_instructions(text):
    """Parse instructions from text."""
    instructions = []
    lines = text.split("\n")
    in_section = False
    step = 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if re.match(
            r"^(?:instructions?|directions?|steps?|method)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = True
            continue
        if re.match(r"^(?:ingredients?)[\s:]*$", line, re.IGNORECASE):
            in_section = False
            continue

        # Numbered or timestamped
        ts = re.match(r"(\d{1,2}:\d{2})\s*[-–]\s*(.+)", line)
        num = re.match(r"^\d+[.)]\s+(.+)", line)

        if ts:
            instructions.append({"step": step, "text": ts.group(2)})
            step += 1
        elif num:
            instructions.append({"step": step, "text": num.group(1)})
            step += 1
        elif in_section and not line.startswith(("-", "*", "•")):
            instructions.append({"step": step, "text": line})
            step += 1

    return instructions[:30]


def fetch_metadata(url):
    """Fetch video metadata from YouTube API."""
    from googleapiclient.discovery import build

    api_key = get_api_key()
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY not configured")

    m = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        url,
    )
    if not m:
        raise ValueError("Invalid YouTube URL")

    video_id = m.group(1)
    youtube = build("youtube", "v3", developerKey=api_key)
    response = youtube.videos().list(part="snippet", id=video_id).execute()

    if not response.get("items"):
        raise ValueError("Video not found")

    snippet = response["items"][0]["snippet"]
    thumbs = snippet.get("thumbnails", {})
    thumb = ""
    for q in ("maxres", "high", "medium", "default"):
        if q in thumbs:
            thumb = thumbs[q]["url"]
            break

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "thumbnail": thumb,
    }


def fetch_transcript(url):
    """Fetch transcript via markitdown."""
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(url)
        return result.text_content or ""
    except Exception:
        return ""


def import_recipe(url, household_id=None):
    """
    Import recipe from YouTube URL.

    Args:
        url: YouTube video URL
        household_id: Optional household ID

    Returns:
        dict: {"success": bool, "recipe_id": int, "title": str,
               "ingredients": int, "instructions": int, "error": str}
    """
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "YOUTUBE_API_KEY not set"}

    try:
        # Get data
        metadata = fetch_metadata(url)
        full_text = metadata["description"]
        try:
            transcript = fetch_transcript(url)
            if transcript:
                full_text = transcript
        except Exception:
            pass

        # Parse
        ingredients = parse_ingredients(full_text)
        instructions = parse_instructions(full_text)

        # Get household
        household = None
        if household_id:
            household = Household.objects.get(id=household_id)
        else:
            household = Household.objects.first()

        if not household:
            return {"success": False, "error": "No household found"}

        # Create recipe
        recipe = Recipe.objects.create(
            title=metadata["title"][:200],
            description=full_text[:5000],
            video_url=url,
            household=household,
            needs_review=True,
        )

        # Add ingredients
        for ing in ingredients:
            ing_obj, _ = Ingredient.objects.get_or_create(
                household=household,
                name__iexact=ing["name"],
                defaults={"household": household, "name": ing["name"]},
            )
            try:
                qty = float(ing["quantity"]) if ing["quantity"] else 1
            except (ValueError, TypeError):
                qty = 1
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ing_obj,
                quantity=qty,
                unit=ing["unit"],
            )

        # Add instructions
        for i, inst in enumerate(instructions, 1):
            Instruction.objects.create(
                recipe=recipe,
                step_number=inst["step"],
                text=inst["text"][:1000],
            )

        return {
            "success": True,
            "recipe_id": recipe.id,
            "title": recipe.title,
            "ingredients": len(ingredients),
            "instructions": len(instructions),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--household-id", type=int)
    args = parser.parse_args()

    result = import_recipe(args.url, args.household_id)
    if result["success"]:
        print(f"✓ Imported: {result['title']}")
        print(f"  Recipe ID: {result['recipe_id']}")
        print(f"  Ingredients: {result['ingredients']}")
        print(f"  Instructions: {result['instructions']}")
    else:
        print(f"✗ Error: {result['error']}")

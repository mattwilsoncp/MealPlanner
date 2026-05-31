"""
Response parser for AI-generated meal plans.

Handles extracting structured JSON meal plans from AI API responses,
including fallback parsing for markdown code fences and embedded JSON.
"""

import json
import logging
import re
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


def parse_weekly_plan(ai_response: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Parse the AI response into a structured list of daily meal plans.

    Accepts either the parsed JSON dict (from _make_api_call which
    calls json.loads) or the raw list directly.

    Returns:
        List of dicts, each with:
            date: str (YYYY-MM-DD)
            meals: list[dict] with meal_type, title, description, cook_time_minutes, ingredients

    Raises:
        ValueError: If the response structure is invalid or days are missing.
    """
    # If it's a dict with a 'days' or 'meals' or 'plan' key, unwrap it
    if isinstance(ai_response, dict):
        for key in ("days", "meals", "plan", "weekly_plan", "data"):
            if key in ai_response:
                content = ai_response[key]
                if isinstance(content, list):
                    ai_response = content
                    break

    if not isinstance(ai_response, list):
        raise ValueError(
            f"Expected a list of daily plans, got {type(ai_response).__name__}"
        )

    if not ai_response:
        raise ValueError("AI returned an empty meal plan")

    parsed_days: list[dict[str, Any]] = []

    for day_entry in ai_response:
        day = _parse_day(day_entry)
        if day and day.get("meals"):
            parsed_days.append(day)

    if not parsed_days:
        raise ValueError("No valid daily meals found in AI response")

    return parsed_days


def _parse_day(day_entry: Any) -> dict[str, Any] | None:
    """Parse a single day entry from the AI response.

    Accepts dict-like objects that may have keys: date, day, day_of_week,
    meals, breakfast, lunch, dinner, snack.
    """
    if not isinstance(day_entry, dict):
        logger.warning("Day entry is not a dict: %s", type(day_entry))
        return None

    # Extract the date string
    date_str = day_entry.get("date") or day_entry.get("day") or day_entry.get("day_of_week")
    if not date_str:
        logger.warning("Day entry missing date field: %s", day_entry)
        return None

    # Validate date format
    try:
        parsed_date = date.fromisoformat(date_str)
        normalized_date = parsed_date.isoformat()
    except (ValueError, TypeError):
        logger.warning("Invalid date format in day entry: %s", date_str)
        return None

    # Extract meals — can be in 'meals' array or as individual keys
    meals: list[dict[str, Any]] = []

    if "meals" in day_entry and isinstance(day_entry["meals"], list):
        for meal_entry in day_entry["meals"]:
            meal = _parse_meal(meal_entry)
            if meal:
                meals.append(meal)
    else:
        # Try individual meal type keys
        for meal_type in (
            "breakfast", "lunch", "dinner", "snack",
            "Breakfast", "Lunch", "Dinner", "Snack",
        ):
            if meal_type in day_entry:
                meal_data = day_entry[meal_type]
                if isinstance(meal_data, dict):
                    meal_data.setdefault("meal_type", meal_type.lower().removesuffix("extra"))
                    meal = _parse_meal(meal_data)
                    if meal:
                        meals.append(meal)
                elif isinstance(meal_data, str):
                    meals.append(_text_only_meal(meal_data, meal_type.lower().removesuffix("extra")))

    if not meals:
        logger.warning("No meals found for day %s", normalized_date)
        return None

    return {
        "date": normalized_date,
        "meals": meals,
    }


def _parse_meal(meal_entry: Any) -> dict[str, Any] | None:
    """Parse a single meal entry."""
    if not isinstance(meal_entry, dict):
        logger.warning("Meal entry is not a dict: %s", type(meal_entry))
        return None

    title = meal_entry.get("title") or meal_entry.get("name") or meal_entry.get("meal")
    if not title:
        logger.warning("Meal entry missing title: %s", meal_entry)
        return None

    meal_type_raw = str(
        meal_entry.get("meal_type")
        or meal_entry.get("type")
        or "dinner"
    ).lower().strip()

    # Normalize meal type
    meal_type = meal_type_raw
    for valid_type in VALID_MEAL_TYPES:
        if valid_type in meal_type_raw:
            meal_type = valid_type
            break
    if meal_type_raw == "launch":
        meal_type = "lunch"

    description = meal_entry.get("description") or meal_entry.get("desc") or ""

    cook_time = meal_entry.get("cook_time_minutes") or meal_entry.get("cook_time") or 30
    try:
        cook_time = int(cook_time)
    except (ValueError, TypeError):
        cook_time = 30

    ingredients = meal_entry.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = [i.strip() for i in ingredients.split(",") if i.strip()]

    return {
        "meal_type": meal_type,
        "title": str(title).strip(),
        "description": str(description).strip(),
        "cook_time_minutes": max(1, cook_time),
        "ingredients": [str(i).strip() for i in ingredients if i],
    }


def _text_only_meal(text: str, meal_type: str) -> dict[str, Any]:
    """Create a meal entry from a text-only value."""
    return {
        "meal_type": meal_type,
        "title": text.strip(),
        "description": "",
        "cook_time_minutes": 30,
        "ingredients": [],
    }

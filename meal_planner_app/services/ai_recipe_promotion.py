"""
AI recipe promotion service.

When ``AiPlanSaveView`` materialises an accepted AI meal, the resulting
``MealPlan`` row is a *stub*: it has no linked ``Recipe`` row, no
``Instruction`` rows, and no ``IngredientLink`` rows. It just records a
title (in ``custom_meal``), a cook time (in ``notes``), and an unordered
list of free-form ingredient strings (in ``ingredients``).

This service exposes a single helper that mounts the same OpenRouter
chat-completion flow used by ``AIService`` (so per-household model
bindings and key overrides are honoured) and asks the model to expand
the stub into a fully-structured recipe::

    {
        "title": "string",
        "description": "string",
        "ingredients": [
            {"name": "string", "quantity": number, "unit": "string"},
            ...
        ],
        "instructions": [
            {"step_number": int, "text": "string"},
            ...
        ]
    }

Failures (missing API key, transient HTTP error, malformed body) are
returned as a ``PromotionOutcome`` with ``success=False`` and a
human-readable ``reason`` — callers fall back to a basic recipe
built from the meal's own data so the click still produces a
useful Recipe row instead of an empty 500 page.

Public surface
- ``promote_meal_to_recipe(meal) -> PromotionOutcome`` — round-trips
  the model and never raises for the documented failure modes.
- ``PromotionOutcome`` dataclass with ``success``, ``title``,
  ``description``, ``ingredients`` (list of dicts), ``instructions``
  (list of dicts), ``reason`` (error description or ``None``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import logging

logger = logging.getLogger(__name__)


PROMOTION_PROMPT_TEMPLATE = """You are rounding out a half-finished meal plan into a real recipe a cook can follow.

The original suggestion came from an AI meal planner; the user has accepted it
and now wants a complete, structured recipe they can save to their library.
Your output is the source of truth for a Recipe row that will be persisted
with linked ingredient rows and instruction rows.

Return ONLY valid JSON with this exact shape:

{{
  "title": "string",
  "description": "string",
  "ingredients": [
    {{"name": "string", "quantity": number, "unit": "string"}}
  ],
  "instructions": [
    {{"step_number": <1-based int>, "text": "string"}}
  ]
}}

Rules:
- Keep the original title unless it is genuinely unclear; if you refine it,
  keep it close to the original.
- The description should be 1-3 sentences of context (origin/cuisine/serving
  suggestion), distinct from the steps.
- Re-use the ingredient names supplied when reasonable. Split combined
  ingredients into separate rows.
- Provide realistic quantities and a sensible cooking unit (oz, lb, cup,
  tbsp, tsp, g, kg, ml, l, piece, clove, slice, bunch, can).
- Instructions are imperative, 1-N steps, ordered starting at 1.
- Do not include markdown, explanation, or code fences — JSON only.

Source meal:
- Title: {title}
- Description: {description}
- Cook time (minutes): {cook_time}
- Ingredient list (free-form, may lack quantities): {ingredients}
"""


@dataclass
class PromotionOutcome:
    """Outcome of a single promotion attempt.

    On success: ``success=True`` and the four content fields are
    populated. On failure: ``success=False`` and ``reason`` carries a
    short, user-friendly explanation; callers fall back to a basic
    recipe built from the meal's own data so a missing API key or a
    malformed AI reply doesn't strand the user on an error page.
    """

    success: bool
    title: str = ""
    description: str = ""
    ingredients: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    reason: str | None = None


def _truncate(value: str, limit: int) -> str:
    value = value or ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def promote_meal_to_recipe(meal: MealPlan) -> PromotionOutcome:  # noqa: F821
    """Ask the OpenRouter chat-completions endpoint to expand *meal*
    into a structured recipe.

    Re-uses the same model-binding and API-key-resolution helpers as
    ``meal_planner_app.services.ai_service.AIService`` so a household's
    per-feature model selection is honoured. Returns a
    ``PromotionOutcome``. Never raises for the documented failure
    modes — only programming errors leak.
    """
    import json
    import re
    from typing import Any as _Any

    import httpx as _httpx

    from .ai_settings import resolve_model, resolve_openrouter_api_key

    household = meal.household
    api_key = resolve_openrouter_api_key(household)
    if not api_key:
        return PromotionOutcome(
            success=False,
            reason=(
                "No OpenRouter API key is configured for this household. "
                "Configure one in Tools → AI Models, or save the basic "
                "recipe built from the meal data."
            ),
        )

    model_id = resolve_model(
        household, "meal_plan_generation", override=None
    )

    title = _truncate(meal.ai_title or meal.custom_meal or "AI Meal", 200)
    description = _truncate(
        meal.ai_description or meal.notes or "",
        500,
    )
    cook_time = meal.ai_cook_time_minutes or 30
    raw_ingredients = meal.ingredients or []
    if isinstance(raw_ingredients, list):
        ingredient_lines = ", ".join(str(i).strip() for i in raw_ingredients if str(i).strip())
    else:
        ingredient_lines = str(raw_ingredients)

    prompt = PROMOTION_PROMPT_TEMPLATE.format(
        title=title,
        description=description or "(none)",
        cook_time=cook_time,
        ingredients=ingredient_lines or "(none)",
    )

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You expand short AI meal-plan stubs into structured "
                    "recipes. You reply with valid JSON only — no "
                    "markdown, no code fences, no prose."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.6,
    }

    try:
        with _httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
    except _httpx.HTTPStatusError as exc:
        logger.warning(
            "AI recipe-promotion attempt rejected for meal %s: HTTP %s — %s",
            meal.pk, exc.response.status_code, exc.response.text[:200],
        )
        return PromotionOutcome(
            success=False,
            reason=(
                f"OpenRouter returned HTTP {exc.response.status_code}. "
                "Saving the basic recipe from the meal data instead."
            ),
        )
    except _httpx.RequestError as exc:
        logger.warning(
            "AI recipe-promotion network failure for meal %s: %s",
            meal.pk, exc,
        )
        return PromotionOutcome(
            success=False,
            reason=(
                f"Could not reach OpenRouter ({type(exc).__name__}). "
                "Saving the basic recipe from the meal data instead."
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "AI recipe-promotion reply was not JSON for meal %s: %s",
            meal.pk, exc,
        )
        return PromotionOutcome(
            success=False,
            reason=(
                "AI reply was not parseable. Saving the basic recipe "
                "from the meal data instead."
            ),
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "AI recipe-promotion unexpected error for meal %s", meal.pk,
        )
        return PromotionOutcome(
            success=False,
            reason=f"Unexpected AI error: {exc}",
        )

    choices = data.get("choices") or []
    if not choices:
        return PromotionOutcome(
            success=False,
            reason="AI reply had no choices; saving the basic recipe.",
        )
    content = (choices[0].get("message") or {}).get("content") or ""
    if not content:
        return PromotionOutcome(
            success=False,
            reason="AI reply was empty; saving the basic recipe.",
        )

    # Parse JSON, allowing for markdown code fences.
    text = content.strip()
    try:
        parsed: dict[str, _Any] = json.loads(text)
    except json.JSONDecodeError:
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", text, flags=re.DOTALL,
        )
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        else:
            array_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if array_match:
                try:
                    parsed = json.loads(array_match.group(0))
                except json.JSONDecodeError:
                    parsed = {}  # type: ignore[assignment]
            else:
                parsed = {}

    if not isinstance(parsed, dict):
        return PromotionOutcome(
            success=False,
            reason="AI reply was not a JSON object; saving the basic recipe.",
        )

    raw_ingredients = parsed.get("ingredients") or []
    instructions = parsed.get("instructions") or []
    raw_title = (parsed.get("title") or "").strip()
    if not raw_title:
        # Title is the only field we strictly require to call this a
        # recipe; without one we degrade to the fallback path.
        return PromotionOutcome(
            success=False,
            reason="AI reply lacked a title; saving the basic recipe.",
        )

    cleaned_ingredients: list[dict[str, _Any]] = []
    for ing in raw_ingredients:
        if not isinstance(ing, dict):
            continue
        name = str(ing.get("name") or "").strip()
        if not name:
            continue
        try:
            quantity = float(ing.get("quantity") or 1)
            if quantity <= 0:
                quantity = 1.0
        except (TypeError, ValueError):
            quantity = 1.0
        unit = str(ing.get("unit") or "piece").strip() or "piece"
        cleaned_ingredients.append(
            {
                "name": name,
                "quantity": quantity,
                "unit": unit,
            }
        )

    cleaned_instructions: list[dict[str, _Any]] = []
    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        text_step = str(inst.get("text") or "").strip()
        if not text_step:
            continue
        try:
            step_number = int(inst.get("step_number") or (len(cleaned_instructions) + 1))
        except (TypeError, ValueError):
            step_number = len(cleaned_instructions) + 1
        cleaned_instructions.append(
            {
                "step_number": max(1, step_number),
                "text": text_step,
            }
        )

    description_out = str(parsed.get("description") or "").strip()

    return PromotionOutcome(
        success=True,
        title=raw_title[:200],
        description=description_out,
        ingredients=cleaned_ingredients,
        instructions=cleaned_instructions,
    )


def basic_recipe_from_meal(meal: MealPlan) -> PromotionOutcome:  # noqa: F821
    """Fallback: build a ``PromotionOutcome`` straight from the meal.

    Used when ``promote_meal_to_recipe`` returns ``success=False`` so
    the user gets a real Recipe row regardless of whether the AI side
    succeeded. Ingredients map to ``(quantity=1, unit="piece")`` and
    instructions list the cook time as a single placeholder note.
    """
    title = (meal.ai_title or meal.custom_meal or "Recipe").strip().rstrip(":").strip()
    if not title:
        title = "Unnamed Recipe"
    description = meal.ai_description or (meal.notes or "")
    cook_time = meal.ai_cook_time_minutes or 30

    ingredients: list[dict[str, Any]] = []
    for raw in meal.ingredients or []:
        name = str(raw).strip()
        if not name:
            continue
        ingredients.append({"name": name, "quantity": 1.0, "unit": "piece"})

    instructions: list[dict[str, Any]] = []
    if ingredients or description:
        instructions.append(
            {
                "step_number": 1,
                "text": (
                    f"Cook the dish for about {cook_time} minutes, "
                    "adjusting seasoning to taste."
                ),
            }
        )

    return PromotionOutcome(
        success=True,
        title=title[:200],
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        reason="basic_recipe_from_meal",
    )

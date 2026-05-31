# Stack Research: AI Meal Suggestions

## API Integration

### opencode.ai /zen/v1 API

- **Endpoint:** `https://opencode.ai/zen/v1/chat/completions`
- **Format:** OpenAI-compatible chat completions (messages array, model, max_tokens, etc.)
- **Auth:** None required (public free API)
- **Cost:** $0 (free tier)
- **Available free models:**
  - `deepseek-v4-flash-free` — Fast, capable for structured output
  - `mimo-v2.5-free` — Alternative option
  - `nemotron-3-super-free` — Larger model option
- **Rate limits:** Unknown — should implement retry with backoff

### Django Integration Approach

1. **Option A: Direct HTTP requests** via `httpx` or `requests` in a Django view/task
   - Simple, no extra dependencies beyond httpx
   - Synchronous — use `httpx` with timeout or background task

2. **Option B: Celery/background task** for async generation
   - Better UX — user doesn't wait at the form
   - Notifications when plan is ready
   - Requires Redis/Celery setup

3. **Option C: Django management command** + polling
   - User triggers command, polls for result
   - Simplest async approach without Celery

### Recommendation

Use **Option A** initially (direct HTTP with httpx in a synchronous view) with a loading spinner. The API is fast (~2-5s for meal plan generation). Keep it simple for v1.2.

If latency becomes an issue, migrate to django-q2 (lightweight task queue, no Redis required for simple use).

### Python Dependencies

- `httpx` — Modern HTTP client with timeout support
- `pydantic` — For structured response parsing (already in Django deps)

## Inventory Data for Prompt Context

Pass to the API as structured context:

```python
inventory_context = {
    "perishable_items": [
        {"name": "Chicken Breast", "quantity": "1 lb", "expires_soon": True},
        {"name": "Spinach", "quantity": "3 cups", "expires_soon": True},
    ],
    "non_perishable_items": [
        {"name": "Rice", "quantity": "2 cups"},
        {"name": "Pasta", "quantity": "1 lb"},
    ],
}
```

## Preference Model

```python
class MealPreferences(models.Model):
    household = models.OneToOneField(Household, on_delete=models.CASCADE)
    cuisine_preferences = ArrayField(models.CharField(max_length=50), default=list)
    dietary_restrictions = ArrayField(models.CharField(max_length=50), default=list)
    cooking_effort = models.CharField(max_length=20, choices=[("quick", "Quick (<30 min)"), ("moderate", "Moderate (30-60 min)"), ("elaborate", "Elaborate (>60 min)")], default="moderate")
    servings_per_meal = models.IntegerField(default=2)
    meals_per_week = models.IntegerField(default=7)
    excluded_ingredients = ArrayField(models.CharField(max_length=100), default=list)
```

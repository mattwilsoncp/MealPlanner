# Architecture Research: AI Meal Suggestions

## Integration Points with Existing Code

### Existing MealPlan Model
- **File:** `meal_planner_app/models.py`
- **Fields:** household, meal_date, meal_type, recipe (FK→Recipe), custom_meal, notes, meal_rating, cooked_at
- AI-generated meals will use `custom_meal` field (since no Recipe model record exists yet)
- Or: create new `Recipe` records for AI-generated recipes? → Too heavy for v1.2, use custom_meal

### Existing Planner View
- **File:** `meal_planner_app/views.py` — `PlannerHomeView`
- Currently loads meal plans for a week, renders planner template
- New flow: user clicks "Generate AI Plan" → POST to new endpoint → returns suggestions

### Existing Inventory Views
- For fetching inventory data to include in AI prompt context
- Already has APIs for listing inventory items

### Existing Shopping List
- Meal plans already generate shopping lists
- AI plan generation should also trigger missing-ingredient calculation

## New Components

### 1. MealPreferences Model
- One-to-one with Household
- Stores cuisine, dietary, effort, servings preferences

### 2. AI Suggestion Service
- `meal_planner_app/services/ai_meal_service.py`
- Orchestrates: gather context → call opencode.ai API → parse response

### 3. AI Plan View
- `POST /meal-planner/ai-generate/` — accepts preferences + date range
- Returns structured meal suggestions as JSON

### 4. AI Plan Review View
- `GET /meal-planner/ai-preview/<session_id>/` — shows AI suggestions
- `POST /meal-planner/ai-accept/` — saves accepted suggestions to MealPlan

## Data Flow

```
User clicks "Generate AI Plan"
  ↓
Client sends POST with:
  - date_range (start, end)
  - preferences (from MealPreferences model)
  - inventory_context (from Inventory model)
  ↓
Server builds structured prompt:
  "Create a 7-day meal plan for 2 people.
   Available inventory: [items near expiry], [pantry items]
   Preferences: [cuisines], [dietary restrictions], [effort level]
   Output JSON: {days: [{date, meal_type, title, description, cook_time, ingredients}]}"
  ↓
Server calls POST https://opencode.ai/zen/v1/chat/completions
  - model: deepseek-v4-flash-free
  - response_format: { type: "json_object" }
  ↓
Parse JSON response → validate schema
  ↓
Store as AIPlanSession (temporary, not committed)
  ↓
Return to client: render preview
  ↓
User accepts → save to MealPlan model
  ↓
Generate shopping list for missing ingredients
```

## Suggested File Changes

| File | Change |
|------|--------|
| `meal_planner_app/models.py` | Add `MealPreferences` model |
| `meal_planner_app/views.py` | Add AI plan views |
| `meal_planner_app/urls.py` | Add AI plan routes |
| `meal_planner_app/services/ai_meal_service.py` | NEW: AI orchestration service |
| `templates/meal_planner/planner.html` | Add "AI Generate" button |
| `templates/meal_planner/ai_preview.html` | NEW: AI plan review page |
| `templates/meal_planner/preferences.html` | NEW: preferences page |

## Build Order (Recommended)

1. **Phase 1:** MealPreferences model + preferences UI page
2. **Phase 2:** AI meal service + opencode.ai API integration
3. **Phase 3:** AI plan generation view + preview UI
4. **Phase 4:** Accept/regenerate/reject workflow + shopping list integration

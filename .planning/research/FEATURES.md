# Features Research: AI Meal Suggestions

## Table Stakes (Must Have for v1.2)

1. **Preference Configuration**
   - User sets dietary restrictions, cuisine preferences, cooking effort
   - Configure servings per meal and meals per week
   - Exclude specific ingredients

2. **One-Click AI Meal Generation**
   - Button on planner page: "Generate AI Meal Plan"
   - Takes 3-10 seconds with loading spinner
   - Generates full week of meals (Mon-Sun or custom range)

3. **AI Output Format**
   - Each day gets a meal type (Breakfast, Lunch, Dinner) with recipe
   - Each AI-generated recipe has: title, brief description, estimated cook time, key ingredients
   - Existing inventory items are prioritized/accounted for

4. **Shopping List Integration**
   - Missing ingredients (not in inventory) are added to shopping list
   - Items already in inventory are noted

5. **Accept / Reject / Regenerate**
   - User can regenerate individual days
   - User can reject and replace specific suggestions
   - Accepting saves the plan to the existing MealPlan model

## Differentiators

1. **Inventory-Aware Generation**
   - AI considers what's about to expire (perishables first)
   - Suggests meals that use expiring ingredients
   - Builds on existing "Use Before It Spoils" feature

2. **Novel Recipe Creation**
   - Generates unique recipe names and instructions (not just existing recipes)
   - Provides estimated prep time and difficulty
   - Descriptions that match user's cuisine preferences

3. **Week Variety**
   - Avoids repeating similar meals in the same week
   - Balances protein sources, cuisines, cooking effort across days

## Anti-Features (Explicitly Not Doing in v1.2)

- Nutritional calculations / calorie counting
- Allergy severity tracking
- Meal prep timeline (when to cook what)
- Collaborative multi-user planning
- Image generation for AI-created recipes
- Export to PDF / grocery list printing

## UX Flow

```
Planner Page → "Generate AI Plan" button
  → Modal: "Using your preferences and inventory..."
  → Loading spinner (3-10s)
  → Preview: Weekly grid with AI-suggested meals
  → Each day: Accept ✓ | Regenerate ⟳ | Reject ✗
  → "Save Plan" saves to database
  → Shopping list updated with missing items
```

## UI Surface Areas

1. **New Preferences Page** — `/meal-planner/preferences/`
   - Cuisine preferences (multi-select tags)
   - Dietary restrictions (checkboxes: vegetarian, vegan, gluten-free, dairy-free, low-carb, keto, etc.)
   - Cooking effort slider
   - Servings per meal
   - Excluded ingredients (free-text tags)

2. **Planner Button** — Existing planner page gets "AI Generate" button
   - Appears alongside existing manual planner controls

3. **AI Plan Review** — Inline preview on planner or dedicated review page
   - Shows full week with AI suggestions
   - Per-day controls (accept/regenerate/reject)
   - "Save All" button

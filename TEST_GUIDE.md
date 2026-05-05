# Unit Test Guide

## Overview

Tests live alongside the code they exercise, inside each app's `tests.py` or
`tests/` directory.  Run the full suite with:

```bash
python manage.py test
```

Coverage reports (requires `coverage`):

```bash
coverage run manage.py test
coverage report --include="**/recipes/**,**/shopping/**,**/inventory/**,**/ingredients/**,**/household/**,**/accounts/**,**/reviews/**,**/tags/**"
```

---

## What Exists

### accounts

**File:** `accounts/tests.py`

`LoginFlowTests`
- `test_login_with_username_redirects` — POSTing a valid username+password redirects to `/`
- `test_login_with_email_redirects` — same for email address as username
- `test_invalid_login_shows_error` — bad credentials return 200 with an error message

**Gaps:**
- Logout view
- Session persistence across requests
- Login required decorator on protected views

---

### household

**File:** `household/tests.py`

`HouseholdModelTests`
- `test_expiring_threshold_defaults_to_seven` — `expiring_threshold_days` defaults to `7`
- `test_expiring_threshold_requires_positive_value` — setting `0` raises `ValidationError`

**Gaps:**
- `name` max-length enforcement
- Unique-together constraint on household name (if any)
- Signal-based teardown when a household is deleted

---

### ingredients

**File:** `ingredients/tests/test_links_and_nutrition.py`

`IngredientLinksAndNutritionTests`
- `test_reconciliation_save_persists_household_inventory_link`
- `test_reconciliation_save_rejects_cross_household_inventory_link`
- `test_ingredient_model_exposes_usda_nutrition_snapshot_fields` — fields `calories_kcal`, `protein_g`, `carbs_g`, `fat_g` exist
- `test_recipe_detail_includes_usda_reference_and_nutrition_in_context`
- `test_recipe_detail_shows_nutrition_empty_state_when_missing`

**Gaps:**
- `IngredientLink` quantity/unit CRUD
- `Ingredient` create/read/update/delete
- Duplicate ingredient name within a household
- `IngredientLinkForm` validation
- Unit normalization

---

### instructions

**File:** `instructions/tests.py` — **empty**

**Gaps:**
- `Instruction` model create/read/update/delete
- `InstructionForm` validation
- Step-number ordering constraints
- Signal: deleting a recipe cascades to its instructions

---

### inventory

**File:** `inventory/tests.py`

`InventoryItemModelTests`
- `test_inventory_item_has_image_field` — field type and `upload_to` path
- `test_inventory_item_keeps_household_indexes` — compound indexes on `(household, name)` and `(household, expiration_date)`

`InventoryFormsTests`
- `test_negative_quantity_is_rejected` — form with `quantity=-1` is invalid
- `test_zero_quantity_is_valid`
- `test_inventory_forms_are_exported`

`InventoryViewTests`
- `test_inventory_urls_exist_for_crud_expiration_and_quick_add`
- `test_inventory_list_applies_household_scope_and_combined_filters`
- `test_edit_and_delete_are_household_scoped` — 404 for cross-household edit/delete
- `test_expiring_and_expired_views_use_household_threshold_rules`

`InventoryQuickAddApiTests`
- `test_quick_add_success_returns_created_item_payload`
- `test_quick_add_invalid_payload_returns_field_errors`
- `test_quick_add_requires_csrf_token`

**Gaps:**
- `InventoryItemForm` full validation (category choices, location choices)
- `InventoryQuickAddForm` isolation
- Image upload handling in views
- Expiration date in the past validation

---

### meal_planner_app

**File:** `meal_planner_app/tests.py` — **empty**

**Gaps:**
- `MealPlan` model: create, cascade delete when recipe/household removed
- `MealType` choices
- `MealPlanCalendarView` — authenticated access, meal type filtering
- Meal assignment via form

---

### ratings

**File:** `ratings/tests.py` — **empty**

**Gaps:**
- `Rating` model: create, unique-together (user, recipe)
- `RatingForm` validation
- Average rating computation on `RecipeDetailView`
- Rating submission via POST
- Cross-user isolation (user A cannot rate user B's recipe directly)

---

### recipes

**File:** `recipes/tests/test_recipe_editing.py`

`RecipeEditingTests`
- `test_recipe_edit_persists_posted_instruction_order_contiguously` — reordering steps renumbers them contiguously from 1
- `test_recipe_edit_can_create_and_attach_new_tag_inline`
- `test_recipe_edit_rejects_duplicate_new_tag_name_within_household`

**Gaps:**
- `RecipeListView` — sort by newest/oldest/rating/title, search filter, household scope
- `RecipeDetailView` — full context including `ingredients`, `instructions`, `ingredient_nutrition`
- `RecipeCreateView` — form rendering, successful creation, validation errors
- `RecipeDeleteView` — confirm page, deletion, redirect
- `RecipeUpdateView` — full update flow (already partially covered by `RecipeEditingTests`)
- `RecipeForm`:
  - `clean_new_tag_name` whitespace normalisation
  - `clean_new_tag_name` case-insensitive duplicate detection
  - `clean_new_tag_name` empty string after whitespace
  - `_save_instruction_order` when no instructions posted
  - `_save_recipe_tags` deselects removed tags
- `ImportForm` and `LLMImportForm`:
  - Valid YouTube URL patterns (`youtube.com`, `youtu.be`)
  - Rejects non-YouTube URLs
  - Optional `title` and `model` fields
- `LLMRecipeImportView`:
  - Redirect to detail page on success
  - Error when `OPENROUTER_API_KEY` is missing
  - Error when video ID extraction fails
  - Error when transcript fetch fails
- Recipe API (`recipes/api.py`):
  - `recipe_list_api` — returns recipe list for household, excludes `needs_review=True`
  - `recipe_search_api` — filters by `title__icontains` and `description__icontains`
  - `recipe_detail_api` — returns ingredients and ordered instructions
  - `recipe_toggle_review` — flips flag, returns JSON
  - All endpoints return 403/302 when unauthenticated

---

### reviews

**File:** `reviews/tests/test_review_queue.py`

`ReviewQueueTests`
- `test_review_queue_and_reconcile_views_render` — both views return 200
- `test_reconciliation_saves_inventory_link`

**Gaps:**
- `ReviewQueue` filters only `needs_review=True` recipes
- `RecipeReconcileView` shows only unreconciled `IngredientLink`s
- Save with no selection (unlink)
- Redirect after save
- Cross-household protection

---

### shopping

**File:** `shopping/tests/test_models.py`

`ShoppingModelScaffoldTests`
- `test_week_is_unique_per_household` — `(household, week_start)` uniqueness

**File:** `shopping/tests/test_discovery_view.py`

`DiscoveryViewTests`
- `test_discovery_view_requires_authentication` — unauthenticated GET redirects to login
- `test_discovery_view_context_is_sorted_urgent_first_and_includes_template_keys`

**File:** `shopping/tests/test_matching.py`

`DiscoveryMatchingServiceTests`
- `test_build_discovery_matches_returns_missing_ingredients_and_urgency_flags`
- `test_build_discovery_matches_orders_urgent_first_then_match_percentage`
- `test_build_discovery_matches_scopes_to_household`

**File:** `shopping/tests/test_generation.py`

`ShoppingGenerationServiceTests`
- `test_generate_week_shopping_list_creates_items_from_meal_plans`
- `test_regenerate_rebuilds_items_for_week` — `regenerate=True` clears; `False` keeps existing
- `test_compute_meal_match_returns_percentage_from_available_and_total`

`ShoppingWeekViewTests`
- `test_week_view_auto_generates_when_missing`
- `test_regenerate_view_forces_rebuild_for_requested_week`
- `test_invalid_week_start_defaults_to_current_monday`

**File:** `shopping/tests/test_shopping_actions.py`

`ShoppingActionEndpointTests`
- `test_toggle_endpoint_flips_checked_state_and_returns_json`
- `test_toggle_endpoint_denies_cross_household_item`
- `test_delete_endpoint_removes_item`
- `test_delete_endpoint_denies_cross_household_item`
- `test_clear_endpoint_deletes_week_items_and_is_idempotent`
- `test_clear_endpoint_does_not_affect_other_household`
- `test_clear_endpoint_when_only_other_household_has_week_returns_zero`

**Gaps:**
- `ShoppingListItem` model: quantity/unit/checked defaults
- `ShoppingListWeek` auto-created on first item add (if applicable)
- `compute_meal_match` edge: recipe with zero ingredients
- `build_discovery_matches` edge: no recipes, no inventory
- Week navigation (previous/next)
- Check-all / uncheck-all
- Item-level quantity edit

---

### tags

**File:** `tags/tests.py` — **empty**

**Gaps:**
- `Tag` model: create with colour, name uniqueness within household
- `RecipeTag` through-model: add/remove tags from recipe
- `TagForm` validation

---

## Example Test Patterns

### View requires login

```python
def test_recipe_list_requires_authentication(self):
    response = self.client.get(reverse("recipes:recipe_list"))
    self.assertEqual(response.status_code, 302)
    self.assertIn("/accounts/login/", response.url)
```

### Form validation

```python
def test_llm_import_form_rejects_non_youtube_url(self):
    form = LLMImportForm(data={"youtube_url": "https://vimeo.com/123456"})
    self.assertFalse(form.is_valid())
    self.assertIn("youtube_url", form.errors)
```

### Cross-household isolation

```python
def test_recipe_detail_denies_other_household(self):
    other_recipe = Recipe.objects.create(
        household=self.other_household,
        title="Private Recipe",
        needs_review=False,
    )
    response = self.client.get(
        reverse("recipes:recipe_detail", args=[other_recipe.id])
    )
    self.assertEqual(response.status_code, 404)
```

### Service function

```python
def test_compute_meal_match_empty_recipe_returns_zero(self):
    result = compute_meal_match(self.recipe, self.inventory_items)
    self.assertEqual(result["match_percentage"], 0.0)
    self.assertEqual(result["available_count"], 0)
```

### Signal / cascade

```python
def test_recipe_delete_cascades_to_instructions(self):
    Instruction.objects.create(recipe=self.recipe, step_number=1, text="Step 1")
    self.recipe.delete()
    self.assertEqual(Instruction.objects.count(), 0)
```

---

## Running Tests

```bash
# All tests
python manage.py test

# Single app
python manage.py test recipes

# Single file
python manage.py test recipes.tests.test_recipe_editing

# With coverage
coverage run manage.py test
coverage html  # generates htmlcov/
```

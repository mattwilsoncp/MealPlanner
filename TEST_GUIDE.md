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
- `test_login_with_username_case_insensitive` — case-insensitive username match
- `test_login_with_email_case_insensitive` — case-insensitive email match
- `test_invalid_login_shows_error` — bad credentials return 200 with an error message
- `test_login_missing_password_fails` — missing password is rejected
- `test_login_missing_username_fails` — missing username/email is rejected
- `test_login_inactive_user_fails` — inactive user cannot log in

`LogoutViewTests`
- `test_logout_redirects_to_login` — GET logout redirects to `/accounts/login/`
- `test_session_is_cleared_after_logout` — session is cleared after logout

`RegisterViewTests`
- `test_register_creates_user_and_household` — valid POST creates user + household, redirects to `/`
- `test_register_creates_default_household_when_no_name_given`
- `test_register_password_mismatch_fails` — mismatched passwords return 200
- `test_register_duplicate_username_fails` — taken username is rejected
- `test_register_success_logs_user_in` — registration automatically logs user in
- `test_register_missing_email_fails` — missing email field is rejected
- `test_register_duplicate_email_fails` — email uniqueness enforced at model+form level

`RegistrationFormTests`
- `test_form_valid_with_all_fields` — form is valid with all fields present
- `test_form_valid_without_household_name` — household name is optional
- `test_form_save_creates_household`
- `test_registration_form_exports` — form is listed in exported forms
- `test_registration_form_requires_email` — email field is required

`UsernameOrEmailBackendTests`
- `test_authenticate_with_username` — plain username works
- `test_authenticate_with_email` — email address works as username
- `test_authenticate_with_username_case_insensitive` — case-insensitive username
- `test_authenticate_with_email_case_insensitive` — case-insensitive email
- `test_authenticate_with_wrong_password_returns_none`
- `test_authenticate_with_nonexistent_user_returns_none`
- `test_authenticate_with_empty_username_and_password_returns_none`
- `test_authenticate_with_empty_email_and_password_returns_none`
- `test_authenticate_with_mixed_case_email_matches` — `User@Example.com` matches `user@example.com`

`CustomUserModelTests`
- `test_str_returns_email` — `str(user)` returns email address
- `test_str_returns_username_when_email_is_empty` — falls back to username
- `test_user_has_nullable_household` — household field can be null

**No major gaps remaining.**

---

### household

**File:** `household/tests.py`

`HouseholdModelTests`
- `test_expiring_threshold_defaults_to_seven` — `expiring_threshold_days` defaults to `7`
- `test_expiring_threshold_requires_positive_value` — setting `0` raises `ValidationError`
- `test_name_max_length_is_enforced` — name > 100 chars raises `ValidationError`
- `test_name_at_max_length_is_valid` — name exactly 100 chars is accepted
- `test_str_returns_name`
- `test_delete_cascades_to_recipes` — deleting household cascades to `Recipe`
- `test_delete_cascades_to_ingredients` — deleting household cascades to `Ingredient`
- `test_delete_cascades_to_inventory_items` — deleting household cascades to `InventoryItem`
- `test_delete_cascades_to_tags` — deleting household cascades to `Tag`
- `test_delete_sets_null_on_custom_user_household` — `CustomUser.household` is `SET_NULL`

**Gaps:**
- `name` uniqueness across households (no unique constraint currently)

**No major gaps remaining.**

---

### ingredients

**File:** `ingredients/tests/test_links_and_nutrition.py`

`IngredientLinksAndNutritionTests`
- `test_reconciliation_save_persists_household_inventory_link`
- `test_reconciliation_save_rejects_cross_household_inventory_link`
- `test_ingredient_model_exposes_usda_nutrition_snapshot_fields` — fields `calories_kcal`, `protein_g`, `carbs_g`, `fat_g` exist
- `test_recipe_detail_includes_usda_reference_and_nutrition_in_context`
- `test_recipe_detail_shows_nutrition_empty_state_when_missing`
- `test_ingredient_create` — basic creation
- `test_ingredient_name_unique_within_household` — duplicate name raises `ValidationError`
- `test_ingredient_name_allowed_across_households` — same name different household is valid
- `test_ingredient_fk_requires_household` — household FK required on create
- `test_ingredient_cascade_deletes_with_household`
- `test_ingredient_link_create`
- `test_ingredient_link_str_includes_ingredient_name`
- `test_ingredient_link_cascade_from_recipe`
- `test_ingredient_link_cascade_from_ingredient`
- `test_ingredient_link_optional_inventory_item`
- `test_ingredient_link_order_preserved`
- `test_nutrition_form_valid_with_all_fields`
- `test_nutrition_form_optional_fields`
- `test_nutrition_form_usda_food_id_max_length`
- `test_nutrition_form_calorie_upper_bound`
- `test_nutrition_form_calorie_negative_rejected`
- `test_reconciliation_form_valid_item`
- `test_reconciliation_form_empty_string_treated_as_none`
- `test_reconciliation_form_none_string_treated_as_none`
- `test_reconciliation_form_rejects_cross_household_item`
- `test_reconciliation_form_invalid_item_id_rejected`

`UnitConversionTests` (`ingredients/utils.py`)
- `test_oz_to_grams`, `test_lb_to_grams`, `test_kg_to_grams`, `test_g_passthrough`
- `test_multiple_oz_to_grams`, `test_cup_to_ml`, `test_tbsp_to_ml`, `test_tsp_to_ml`, `test_ml_passthrough`, `test_l_to_ml`
- `test_piece_count_not_converted`, `test_clove_count_not_converted`, `test_unknown_unit_returns_value_unchanged`
- `test_decimal_input`, `test_string_input`, `test_whitespace_normalized`, `test_case_insensitive`
- `test_grams_to_oz`, `test_grams_to_lb`, `test_grams_to_kg`, `test_grams_to_g`, `test_grams_to_ml`, `test_grams_to_count_passthrough`
- `test_normalize_unit_key_*` — canonical keys for weight/volume/count units
- `test_flour_oz_matches_flour_g` — integration: 3oz = 85.05g matches 100g flour

**Unit normalization: implemented in `ingredients/utils.py`** — `convert_to_grams`, `convert_from_grams`, `normalize_unit_key`. All units normalized to grams (weight) or ml (volume) in shopping list aggregation. Shopping service updated to use canonical units when matching recipe ingredients against inventory. **No remaining gaps.**
- `test_ingredient_requires_household`
- `test_ingredient_delete_cascades_from_household`

`IngredientLinkModelTests`
- `test_create_ingredient_link`
- `test_ingredient_link_str`
- `test_ingredient_link_delete_cascades_from_recipe`
- `test_ingredient_link_delete_cascades_from_ingredient`
- `test_ingredient_link_optional_inventory_item`
- `test_ingredient_link_ordering`

`IngredientNutritionFormTests`
- `test_valid_nutrition_data`
- `test_nutrition_fields_all_optional`
- `test_usda_food_id_too_long_rejected`
- `test_usda_food_id_at_max_length_accepted`
- `test_calories_upper_bound_enforced`
- `test_negative_calories_rejected`

`IngredientLinkReconciliationFormTests`
- `test_valid_inventory_item`
- `test_empty_inventory_item_returns_none`
- `test_none_string_returns_none`
- `test_cross_household_item_rejected`
- `test_invalid_id_rejected`

**Gaps:**
- Unit normalization (converting between `oz`/`g`/`ml` equivalents)

**No major gaps remaining.**

---

### instructions

**File:** `instructions/tests/test_models.py`

`InstructionModelTests`
- `test_create_instruction` — basic creation with recipe, step_number, text
- `test_str_returns_step_number` — `str(step)` returns `"Step N"`
- `test_str_with_high_step_number` — handles step 99+
- `test_ordering_by_step_number` — default Meta ordering is step_number ASC
- `test_recipe_cascade_deletes_instructions` — deleting recipe removes all its steps
- `test_same_recipe_can_have_many_steps` — up to 5 steps
- `test_different_recipes_have_independent_instructions` — instructions scoped to recipe
- `test_step_number_allows_zero` — 0 is a valid step number
- `test_text_field_accepts_long_content` — TextField handles 1000+ chars
- `test_text_cannot_be_blank` — ValidationError on empty text
- `test_step_number_required` — ValidationError when missing
- `test_image_field_is_blankable` — image is optional

**No remaining gaps.** (Note: `InstructionForm` lives in `recipes.forms`, not `instructions/forms.py`.)

---

### inventory

**File:** `inventory/tests/test_main.py`

`InventoryItemModelTests`
- `test_inventory_item_has_image_field` — field type and `upload_to` path
- `test_inventory_item_keeps_household_indexes` — compound indexes on `(household, name)` and `(household, expiration_date)`

`InventoryFormsTests`
- `test_inventory_forms_are_exported`
- `test_negative_quantity_is_rejected`
- `test_zero_quantity_is_valid`

`InventoryViewTests`
- `test_inventory_urls_exist_for_crud_expiration_and_quick_add`
- `test_inventory_list_applies_household_scope_and_combined_filters`
- `test_edit_and_delete_are_household_scoped`
- `test_expiring_and_expired_views_use_household_threshold_rules`

`InventoryQuickAddApiTests`
- `test_quick_add_success_returns_created_item_payload`
- `test_quick_add_invalid_payload_returns_field_errors`
- `test_quick_add_requires_csrf_token`

**File:** `inventory/tests/test_forms_and_views.py`

`InventoryItemModelTests`
- `test_str_includes_name_and_quantity_and_unit`
- `test_str_with_integer_quantity`
- `test_household_cascade_deletes_items`
- `test_cross_household_access_is_denied`

`InventoryItemFormTests`
- `test_form_valid_with_minimal_required_fields`
- `test_form_rejects_invalid_category`
- `test_form_rejects_invalid_location`
- `test_form_accepts_all_valid_categories`
- `test_form_accepts_all_valid_locations`
- `test_form_expiration_date_past_is_not_rejected` — past dates currently accepted
- `test_form_expiration_date_future_is_valid`
- `test_form_barcode_is_optional`
- `test_form_notes_are_optional`
- `test_form_saves_all_fields`

`InventoryQuickAddFormTests`
- `test_quick_add_form_rejects_negative_quantity`
- `test_quick_add_form_accepts_zero_quantity`
- `test_quick_add_form_requires_name`
- `test_quick_add_form_requires_category`
- `test_quick_add_form_requires_location`

`InventoryViewAccessTests`
- `test_create_view_requires_login`
- `test_list_view_requires_login`
- `test_create_view_assigns_household_from_user`
- `test_update_view_assigns_household_from_user`
- `test_update_other_household_returns_404`
- `test_delete_other_household_returns_404`
- `test_delete_own_item_succeeds`
- `test_list_view_only_shows_own_household_items`

**Gaps:**
- Expiration date in the past validation (not currently enforced at form level — `test_form_expiration_date_past_is_not_rejected` documents the current behavior)
- Image upload handling in views
- Barcode form validation (barcode format, length)

---

### meal_planner_app

**File:** `meal_planner_app/tests.py`

`MealPlanModelTests`
- `test_create_mealplan_with_recipe` — basic creation with recipe assigned
- `test_create_mealplan_with_custom_meal` — creation with custom_meal (no recipe)
- `test_create_mealplan_with_notes_and_rating` — notes and meal_rating fields stored correctly
- `test_delete_household_cascades_to_mealplans` — deleting household cascades to MealPlan
- `test_delete_recipe_sets_null_on_mealplan` — deleting recipe sets FK to NULL (SET_NULL)
- `test_unique_constraint_prevents_duplicate` — unique together prevents duplicate entries
- `test_same_type_different_date_is_valid` — same type on different dates is allowed
- `test_str_with_recipe` — `__str__` returns recipe title
- `test_str_with_custom_meal` — `__str__` falls back to custom_meal
- `test_str_with_no_meal_returns_placeholder` — `__str__` with neither recipe nor custom_meal returns "No meal"
- `test_is_custom_true_when_no_recipe` — `is_custom` is True when meal has no recipe
- `test_is_custom_false_when_recipe` — `is_custom` is False when meal has a recipe
- `test_ordering_by_date_and_type` — default Meta ordering is date ASC, type ASC

`MealTypeTests`
- `test_meal_type_choices_exist` — all four meal types (breakfast/lunch/dinner/snack) exist
- `test_meal_type_display_values` — display labels are human-readable
- `test_meal_type_choices_length` — exactly 4 meal type choices

`SideDishModelTests`
- `test_create_side_dish_with_recipe` — SideDish creates with recipe FK
- `test_create_side_dish_with_custom_side` — SideDish creates with custom_side string
- `test_delete_meal_plan_cascades_to_side_dishes` — deleting MealPlan cascades to SideDish
- `test_side_dish_ordering` — SideDishes ordered by order field
- `test_str_with_recipe` — `__str__` returns recipe title
- `test_str_with_custom_side` — `__str__` returns custom_side string

`PlannerHomeViewTests`
- `test_unauthenticated_redirects_to_login` — unauthenticated GET redirects to login
- `test_authenticated_returns_200` — authenticated GET returns 200
- `test_view_shows_only_own_household_meals` — planner only shows meals from user's household
- `test_week_navigation_redirects_to_correct_week` — week navigation redirects to correct year/week URL
- `test_week_navigation_prev_week` — navigating backward redirects correctly
- `test_planner_week_url_with_year_week_loads_correct_week` — /planner/<year>/<week>/ loads correct date range
- `test_json_week_meals_returns_only_own_meals` — json_week_meals API is household-scoped
- `test_planner_context_includes_meal_types` — context includes all four meal types

`MealPlanFormTests`
- `test_form_valid_with_recipe` — form is valid when recipe is provided
- `test_form_valid_with_custom_meal` — form is valid when custom_meal is provided
- `test_form_invalid_when_neither_recipe_nor_custom_meal` — form rejects when both are empty
- `test_form_filters_recipes_to_household` — recipe queryset is filtered to user's household
- `test_form_excludes_needs_review_recipes` — recipes with needs_review=True are excluded

`AddMealViewTests`
- `test_add_meal_requires_login` — unauthenticated GET redirects to login
- `test_add_meal_get_returns_form` — authenticated GET returns 200 with form
- `test_add_meal_post_creates_mealplan` — valid POST creates MealPlan for user's household
- `test_add_meal_with_custom_meal` — POST with custom_meal creates custom meal entry
- `test_add_meal_prefills_from_query_params` — date/type/recipe pre-filled from query string

`AddMealViewSideDishesTests`
- `test_add_meal_with_side_dish_custom` — custom side dish is created alongside meal
- `test_add_meal_with_side_dish_recipe` — side dish linked to recipe is created

`EditMealViewTests`
- `test_edit_meal_get_returns_form` — authenticated GET returns 200 with populated form
- `test_edit_meal_post_updates_mealplan` — valid POST updates MealPlan fields
- `test_edit_other_household_meal_returns_404` — editing another household's meal returns 404

`DeleteMealViewTests`
- `test_delete_meal_removes_mealplan` — POST deletes the MealPlan
- `test_delete_other_household_returns_404` — deleting another household's meal returns 404

`RateMealViewTests`
- `test_rate_meal_with_valid_rating` — POST with rating 1-5 updates meal_rating
- `test_rate_meal_invalid_rating_returns_400` — rating > 5 returns 400
- `test_rate_meal_zero_returns_400` — rating < 1 returns 400
- `test_rate_other_household_returns_404` — rating another household's meal returns 404

`RecipeSelectViewTests`
- `test_recipe_select_excludes_needs_review` — API excludes recipes needing review
- `test_recipe_select_requires_auth` — unauthenticated request returns 302

**Gaps:** None remaining. All originally listed gaps are covered.

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

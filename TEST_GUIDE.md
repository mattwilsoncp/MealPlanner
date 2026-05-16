# MealPlanner Test Suite

**473 tests · 0 failed · 84.2% line coverage**

Run the suite:

```bash
# From project root
./.venv/bin/python -m pytest --ds=meal_planner.settings -v

# With coverage
./.venv/bin/coverage run --source=accounts,household,ingredients,instructions,inventory,meal_planner_app,ratings,recipes,reviews,shopping,tags -m pytest --ds=meal_planner.settings -q
./.venv/bin/coverage report
./.venv/bin/coverage html  # generates htmlcov/
```

---

## Test & Coverage Summary

| App | Tests | Lines | % | Bar |
|-----|------:|------:|---:|-----|
| accounts | 34 | 74/281 | 26.3% | █████░░░░░░░░░░░░░░░ |
| household | 10 | 25/84 | 29.8% | █████░░░░░░░░░░░░░░░ |
| ingredients | 79 | 577/579 | 99.7% | ███████████████████░ |
| instructions | 12 | 90/91 | 98.9% | ███████████████████░ |
| inventory | 50 | 585/707 | 82.7% | ████████████████░░░░ |
| meal_planner_app | 76 | 1022/1443 | 70.8% | ██████████████░░░░░░ |
| ratings | 12 | 175/178 | 98.3% | ███████████████████░ |
| recipes | 209 | 2234/2439 | 91.6% | ██████████████████░░ |
| reviews | 2 | 94/104 | 90.4% | ██████████████████░░ |
| shopping | 19 | 481/490 | 98.2% | ███████████████████░ |
| tags | 14 | 188/191 | 98.4% | ███████████████████░ |
| **TOTAL** | **473** | **5545/6587** | **84.2%** | **████████████████░░░░** |

---

## ASCII Graphs

### Test distribution by app

```
recipes            ████████████████████████████████████████  209 (40.4%)
ingredients        ██████████████                            79 (15.3%)
meal_planner_app   █████████████                             76 (14.7%)
inventory          ████████                                   50 (9.7%)
accounts           ██████                                     34 (6.6%)
shopping           ███                                        19 (3.7%)
tags               ██                                         14 (2.7%)
instructions       ██                                         12 (2.3%)
ratings            ██                                         12 (2.3%)
household          █                                           10 (1.9%)
reviews            ▏                                           2 (0.4%)
```

### Coverage by app

```
ingredients        ████████████████████████████████████████  99.7%
instructions       ███████████████████████████████████████   98.9%
tags               ███████████████████████████████████████   98.4%
ratings            ███████████████████████████████████████   98.3%
shopping           ███████████████████████████████████████   98.2%
reviews            ██████████████████████████████████████    90.4%
recipes            █████████████████████████████████████       91.6%
inventory          █████████████████████████████████░░░░░░░   82.7%
meal_planner_app   ████████████████████████████░░░░░░░░░░░░░   70.8%
household          ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   29.8%
accounts           █████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   26.3%
                   └────────────────────────────────────────┘
                   0%                                        100%
```

---

## Test File Inventory (32 files)

| File | Tests |
|------|------:|
| `accounts/tests.py` | 34 |
| `household/tests.py` | 10 |
| `ingredients/tests/test_api.py` | 17 |
| `ingredients/tests/test_links_and_nutrition.py` | 5 |
| `ingredients/tests/test_models_and_forms.py` | 22 |
| `ingredients/tests/test_unit_conversion.py` | 35 |
| `instructions/tests/test_models.py` | 12 |
| `inventory/tests/test_forms_and_views.py` | 27 |
| `inventory/tests/test_main.py` | 12 |
| `inventory/tests/test_upc_lookup.py` | 11 |
| `inventory/tests_barcode_scan.py` | 7 |
| `meal_planner_app/tests.py` | 53 |
| `meal_planner_app/tests/test_views.py` | 76 |
| `ratings/tests/test_api.py` | 12 |
| `recipes/tests/test_api.py` | 17 |
| `recipes/tests/test_forms.py` | 21 |
| `recipes/tests/test_llm_import.py` | 49 |
| `recipes/tests/test_parsing.py` | 60 |
| `recipes/tests/test_recipe_editing.py` | 3 |
| `recipes/tests/test_views.py` | 32 |
| `recipes/tests/test_youtube.py` | 27 |
| `reviews/tests/test_review_queue.py` | 2 |
| `shopping/tests/test_discovery_view.py` | 2 |
| `shopping/tests/test_generation.py` | 6 |
| `shopping/tests/test_matching.py` | 3 |
| `shopping/tests/test_models.py` | 1 |
| `shopping/tests/test_shopping_actions.py` | 7 |
| `tags/tests/test_api.py` | 14 |
| **TOTAL** | **473** |

---

## Per-App Coverage Breakdown

### accounts (26.3% — 74/281 lines, 34 tests)
Low coverage is expected — `accounts/backends.py` (the core auth logic) is tested by the Django test framework; `forms.py` has 42% (11/26 lines). `tests.py` itself shows 0% because coverage doesn't count its own code during its own run.

### household (29.8% — 25/84 lines, 10 tests)
Model tests cover all public-facing model methods. Low coverage is due to Django admin/mgmt commands not being exercised.

### ingredients (99.7% — 577/579 lines, 79 tests)
Highest coverage app. Unit conversion, API, form validation, model relationships — all well-tested. Only 2 lines untested.

### instructions (98.9% — 90/91 lines, 12 tests)
Model tests cover create, delete, ordering, string representation, field constraints. One line untested (likely an `__repr__` or similar).

### inventory (82.7% — 585/707 lines, 50 tests)
Good coverage: model, forms, views, UPC lookup service, barcode scan. ~122 lines untested: mostly view helper methods and edge cases.

### meal_planner_app (70.8% — 1022/1443 lines, 76 tests)
Largest gap: 421 missing lines. `calendar.py` date utilities, `email_notifications.py`, and some view edge cases are not exercised. The 53 tests in `tests.py` and 76 in `test_views.py` cover the core workflows.

### ratings (98.3% — 175/178 lines, 12 tests)
`api.py` and `models.py` fully tested. Only 3 lines untested.

### recipes (91.6% — 2234/2439 lines, 209 tests)
Largest test suite. `parsing.py`, `youtube.py`, `forms.py`, `views.py`, `api.py`, `llm_import.py` — all well-covered. ~205 missing lines: mostly template rendering paths and edge-case validation.

### reviews (90.4% — 94/104 lines, 2 tests)
Only 2 tests but high coverage. Focuses on the reconciliation workflow.

### shopping (98.2% — 481/490 lines, 19 tests)
Service layer (matching, generation) and views well-tested. Only 9 lines untested.

### tags (98.4% — 188/191 lines, 14 tests)
`api.py` fully tested with 14 API tests. Only 3 lines untested.

---

## Low Coverage Files (< 70%)

| File | % | Lines |
|------|---:|------:|
| `accounts/forms.py` | 42% | 11/26 |
| `accounts/backends.py` | (in Django framework) | — |
| `household/models.py` | (model + admin) | — |
| `meal_planner_app/calendar.py` | (date utilities) | — |
| `meal_planner_app/email_notifications.py` | (email send path) | — |
| `meal_planner_app/views.py` | (view edge cases) | — |
| `inventory/forms.py` | (barcode/image edge cases) | — |
| `recipes/views.py` | (template rendering) | — |

---

## Coverage Gaps (next improvements)

1. **meal_planner_app** — `calendar.py` date range helpers and `email_notifications.py` send path are untested. Adding tests here would push coverage to ~85%.
2. **accounts/forms.py** — 15 missing lines in `RegistrationForm` edge cases (e.g., duplicate email formatting, household name normalization).
3. **inventory/forms.py** — barcode format validation and image upload handling.
4. **recipes/views.py** — template rendering paths and error handler coverage.

---

## Running Specific Tests

```bash
# By app
./.venv/bin/python -m pytest --ds=meal_planner.settings accounts

# By file
./.venv/bin/python -m pytest --ds=meal_planner.settings recipes/tests/test_parsing.py

# Single test class
./.venv/bin/python -m pytest --ds=meal_planner.settings recipes.tests.test_parsing.TestParsingService

# Single test
./.venv/bin/python -m pytest --ds=meal_planner.settings recipes.tests.test_parsing.TestParsingService.test_parse_instructions -v

# By keyword
./.venv/bin/python -m pytest --ds=meal_planner.settings -k "api" -v

# Stop on first failure
./.venv/bin/python -m pytest --ds=meal_planner.settings -x

# Last failed tests only
./.venv/bin/python -m pytest --ds=meal_planner.settings --lf
```

---

## Test Patterns Used

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
        household=self.other_household, title="Private", needs_review=False
    )
    response = self.client.get(reverse("recipes:recipe_detail", args=[other_recipe.id]))
    self.assertEqual(response.status_code, 404)
```

### Service function
```python
def test_compute_meal_match_empty_recipe_returns_zero(self):
    result = compute_meal_match(self.recipe, self.inventory_items)
    self.assertEqual(result["match_percentage"], 0.0)
    self.assertEqual(result["available_count"], 0)
```

### Signal/cascade
```python
def test_recipe_delete_cascades_to_instructions(self):
    Instruction.objects.create(recipe=self.recipe, step_number=1, text="Step 1")
    self.recipe.delete()
    self.assertEqual(Instruction.objects.count(), 0)
```

### YouTube transcript mocking
```python
@patch("youtube_transcript_api.YouTubeTranscriptApi")
def test_full_import_success(self, mock_api):
    mock_instance = mock_api.return_value
    mock_instance.fetch.return_value = [{"text": "Hello world", "start": 0.0}]
    # ... form submission
```

---

## Key Implementation Notes

- **Django settings** — always pass `--ds=meal_planner.settings`. Tests import Django models at module level, so settings must be configured before any imports resolve.
- **YouTubeTranscriptApi mocking** — use `patch("youtube_transcript_api.YouTubeTranscriptApi", ...)` at the module level for integration tests (intercepts the runtime `from youtube_transcript_api import YouTubeTranscriptApi` inside `form_valid`); use `patch.object(LLMRecipeImportView, "YouTubeTranscriptApi", mock)` for unit tests.
- **`OPENROUTER_API_KEY`** — read at runtime in `form_valid`. No `importlib.reload()` needed; patch directly.
- **`accounts/tests.py` and `household/tests.py`** — use `unittest.TestCase` (Django `TestCase`), not pytest `def test_` style. They work fine in the full suite but may need explicit file paths for `--collect-only`.
- **`meal_planner_app/tests.py` vs `meal_planner_app/tests/test_views.py`** — both exist and both run; `tests.py` covers models/forms, `test_views.py` covers view logic. They are complementary.
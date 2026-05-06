---
name: test-gap-filler
description: "Fill test gaps for a Django app: audit gaps from TEST_GUIDE.md, write tests, verify, update docs, commit."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [testing, django, quality, coverage, tdd]
    related_skills: [test-driven-development, systematic-debugging]
---

# Test Gap Filler

## Overview

Fill empty or incomplete test suites for a Django app using `TEST_GUIDE.md` as the source of truth. The workflow: audit → read source code → write tests → run → update docs → commit.

**Assumes:** The project has a `TEST_GUIDE.md` listing what exists and what's missing per app.

## When to Use

- An app has `tests.py` that is empty or has few tests
- `TEST_GUIDE.md` lists concrete gaps for an app
- User says "fill the gaps for X" or "expand tests for X"

## Prerequisites

1. Read `TEST_GUIDE.md` for the target app's section to understand what exists and what's missing
2. Read the app's `models.py`, `views.py`, `forms.py`, `urls.py`, and any service modules
3. Check `AUTHENTICATION_BACKENDS` in settings if auth is involved

## Workflow

### Step 1: Audit the Gap List

For each gap in `TEST_GUIDE.md` for the target app, classify it:

| Gap type | What to write |
|---|---|
| Model gap | `TestCase` with `setUp()` creating the model, testing field defaults/constraints |
| Form gap | `form.is_valid()` with valid/invalid data, `assertIn/NotIn(field.errors, ...)` |
| View gap | `self.client.get/post()` → assert status code, redirect, or context |
| Auth gap | `self.client.login()` + protected view, or `authenticate(request=None, ...)` for backends |
| Service gap | Call the function directly → assert return value |
| Signal/cascade gap | Create related objects, delete parent, assert cascade |

### Step 2: Write Tests

Follow Django TestCase conventions:

```python
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

class AppNameModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Test Home")

    def test_model_field_default(self):
        obj = MyModel.objects.create(household=self.household, name="Test")
        self.assertEqual(obj.field, "expected_default")
```

**Authenticate calls** for backend tests:
```python
backend = MyBackend()
user = backend.authenticate(request=None, username="foo", password="bar")
```

**Form errors** (TemplateResponse has no `is_bound`):
```python
response = self.client.post(reverse("app:view"), data)
form = response.context["form"]
self.assertIn("field", form.errors)
self.assertEqual(form.errors["field"], ["Error message"])
```

**Cross-household isolation:**
```python
def test_view_denies_other_household(self):
    other_recipe = Recipe.objects.create(
        household=self.other_household, title="Private", needs_review=False
    )
    response = self.client.get(reverse("recipes:recipe_detail", args=[other_recipe.id]))
    self.assertEqual(response.status_code, 404)
```

### Step 3: Run Tests

```bash
# Single app, verbose
python manage.py test <app_name> --verbosity=2

# Single test file
python manage.py test <app_name>.tests.<TestClass>.<test_name> --verbosity=2

# Run until all pass, fix failures inline
```

**Typical failures and fixes:**
- `AttributeError: 'TemplateResponse' object has no attribute 'is_bound'` → get form from `response.context["form"]` first
- `AssertionError: assertFormError` fails → use `response.context["form"].errors` instead
- `request=None` on `authenticate()` → pass `request=None` explicitly (Django auth backend signature requires it)
- `ValidationError` expected but not raised → check the field uses `validators=` not just `choices=`

### Step 4: Update TEST_GUIDE.md

After all tests pass, update the app's section in `TEST_GUIDE.md`:
- Add each new test to the "What Exists" list with a one-line description
- Remove the gap from the "Gaps" list (or remove the entire Gaps section if all are filled)
- Mark as `**No major gaps remaining.**` if applicable

Format:
```markdown
`TestClassName`
- `test_name` — one-line description of what it asserts
```

### Step 5: Commit

```bash
git add <app>/tests.py TEST_GUIDE.md
git commit -m "test(<app>): fill gaps — <n> tests added, covers <areas>"
git push origin main
```

## Example

Filling gaps for `accounts` (expanded from 3 → 34 tests):

1. Read `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`, `accounts/backends.py`
2. Write 8 test classes covering login, logout, registration, auth backend, user model
3. Run `python manage.py test accounts --verbosity=2` → all 34 pass
4. Update `TEST_GUIDE.md` accounts section — replace gap list with full test inventory
5. Commit with message describing scope

## Key Patterns

| Pattern | Approach |
|---|---|
| View returns 200 with form errors | `self.assertEqual(response.status_code, 200)` + inspect `response.context["form"].errors` |
| View redirects on success | `self.assertEqual(response.status_code, 302)` + `self.assertRedirects(response, expected_url)` |
| Duplicate email/username rejected | Add `unique=True` to model field AND `clean_field()` to form |
| Auth backend test | `backend.authenticate(request=None, ...)` — `request` is required positional arg |
| Session cleared after logout | Login, logout, `self.assertNotIn(session_key, self.client.session)` |
| Form level uniqueness (before DB) | `clean_email()` → `ValidationError` if `Model.objects.filter(...).exists()` |

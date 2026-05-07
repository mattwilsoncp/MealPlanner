# Meal Planner App v2

A weekly meal planner for households — plan meals by ISO week, import recipes from YouTube, track what you have in the pantry, and auto-generate shopping lists.

```
        MON        TUE        WED        THU        FRI        SAT        SUN
     ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
BRK  │ Overnight│ Yogurt  │ Toast & │ Smoothie│ Avocado │ Pancakes│ Omelette│
     │ Oats     │ Parfait │ Eggs    │ Bowl    │ Toast   │ w/bacon │         │
LCH  │ Leftover│ Chicken │ Tacos   │ Pasta   │ Salad   │ Pizza   │ BBQ     │
     │ Pasta    │ Wrap    │         │         │         │ Night   │ Chicken │
DNR  │ Salmon   │ Stir    │ Meat    │ Burgers │ Thai    │ Salmon  │ Roast   │
     │ & Rice   │ Fry     │ Loaf    │        │ Curry   │         │ Chicken │
     └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
```

## What's inside

| Feature | What it does |
|---------|-------------|
| **Weekly Planner** | ISO week grid — navigate forward/back, add meals to any slot, rate them |
| **Recipe Library** | Add recipes manually or import from a YouTube URL |
| **Side Dishes** | Attach multiple sides (recipe or free-text) to any meal entry |
| **On-Hand Ideas** | Star recipes as "on-hand" for quick-inspiration filtering |
| **Pantry / Inventory** | Track what ingredients you have; shopping list subtracts what you've got |
| **Shopping Lists** | One-click generate from a date range; grouped by aisle-style category |
| **Review Queue** | New recipes land in review before they appear in meal planning |
| **Household-scoped** | All data — recipes, plans, inventory — is scoped to your household |

## Quick Start

```bash
# 1. Clone & set up
git clone https://github.com/mattwilsoncp/meal_planner_app_v2.git
cd meal_planner_app_v2
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# 2. Run
./start_meal_planner.sh
# → http://192.168.4.28:8000
```

Or with systemd (user-level, no `User=` line needed):

```bash
systemctl --user enable --now meal-planner
```

## Key URLs

| URL | What it is |
|-----|-----------|
| `/` | Planner home — current week's meal grid |
| `/planner/<year>/<week>/` | Any ISO week directly |
| `/recipes/` | Recipe library |
| `/recipes/import/` | YouTube URL importer |
| `/inventory/` | Pantry ingredient tracking |
| `/shopping/` | Shopping list generator |
| `/admin/` | Django admin (superuser only) |

## Design

Dark-mode-native, Supabase-inspired aesthetic:

- `#171717` page background, `#0f0f0f` card/button surfaces
- `#3ecf8e` / `#00c573` green accent — used sparingly for brand identity
- `#fafafa` primary text, `#898989` muted
- Border-defined depth (no box shadows): `#2e2e2e` → `#363636` → `#393939`
- Pill-shaped primary buttons (9999px radius), 6px for secondary/ghost
- Source Code Pro for uppercase technical labels; Circular for everything else

See [`DESIGN.md`](./DESIGN.md) for the full design system reference.

## Tech Stack

- **Django 6.0** — Python 3, SQLite (dev), allauth-free custom user model
- **YouTube API** + **markitdown** — transcript parsing for recipe import
- **OpenAI** — optional recipe summarization
- **Django sessions + custom backend** — email or username login

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | No | YouTube Data API v3 — enables video metadata lookup |
| `OPENAI_API_KEY` | No | Enables AI recipe summarization in the YouTube importer |

## Apps

```
accounts          — CustomUser with email+household
household         — Household model (join table for shared data)
recipes           — Recipe CRUD, YouTube import, parsing
ingredients       — Ingredient definitions, unit conversion, nutrition fields
instructions      — Step-by-step recipe instructions
tags              — Tag recipes
ratings           — Per-recipe star rating (1–5)
reviews           — needs_review queue gate for meal planning
inventory         — Pantry: what you have on hand
shopping          — Shopping list generation from planned meals
meal_planner_app  — MealPlan, MealType, SideDish models + views
```

## Project Structure

```
meal_planner_app_v2/
├── accounts/
├── household/
├── recipes/           ← YouTube importer lives here
├── ingredients/
├── instructions/
├── tags/
├── ratings/
├── reviews/
├── inventory/
├── shopping/          ← Shopping list generation
├── meal_planner_app/  ← Core planner: MealPlan, SideDish, week views
├── meal_planner/      ← URL routing, WSGI, settings
├── templates/         ← base.html + app template dirs
├── media/             ← Uploaded recipe photos
├── logs/              ← App logs
├── start_meal_planner.sh
├── meal-planner.service
├── manage.py
├── requirements.txt
└── DESIGN.md
```

## License

MIT — built for personal use, shared freely.
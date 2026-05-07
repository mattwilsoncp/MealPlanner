# Meal Planner App v2

A Django-based weekly meal planner with recipe management, household support, inventory tracking, and smart shopping list generation.

## Features

- **Weekly Meal Planner** — ISO week-based planning view with breakfast/lunch/dinner/snack slots per day
- **Recipe Management** — Add, edit, and organize recipes with ingredients and step-by-step instructions
- **YouTube Importer** — Import recipes from YouTube video descriptions via URL
- **Household Multi-User** — Share a household; recipes and meal plans are scoped per household
- **Inventory Tracking** — Track what ingredients you have on hand
- **Shopping Lists** — Auto-generate shopping lists from planned meals, accounting for inventory
- **Recipe Reviews** — Flag recipes for review before they appear in meal planning
- **Ratings** — Rate recipes to surface favorites in the planner
- **Side Dishes** — Attach multiple side dishes (recipe or custom) to any meal plan entry
- **On-Hand Ideas** — Mark recipes as "on-hand idea" for quick meal inspiration

## Tech Stack

- **Django 6.0** (Python 3)
- **SQLite** (development)
- **YouTube API / markitdown** for recipe import
- **OpenAI** for recipe summarization (optional)

## Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom user model, email authentication |
| `household` | Household model shared by all other apps |
| `recipes` | Recipe CRUD, YouTube import, parsing |
| `ingredients` | Ingredient definitions and unit conversion |
| `instructions` | Step-by-step recipe instructions |
| `tags` | Tag recipes |
| `ratings` | Recipe star ratings |
| `reviews` | Recipe review/approval queue |
| `inventory` | Track on-hand ingredients |
| `shopping` | Generate shopping lists from meal plans |
| `meal_planner_app` | Weekly planner views and meal plan model |
| `meal_planner` | URL routing and settings |

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (for admin access)
python manage.py createsuperuser

# Run the dev server
python manage.py runserver
```

## Running

```bash
./start_meal_planner.sh
# Or manually:
source .venv/bin/activate
python manage.py runserver 192.168.4.28:8000
```

## systemd Service (user-level)

```ini
# ~/.config/systemd/user/meal-planner.service
[Unit]
Description=Meal Planner App v2

[Service]
WorkingDirectory=%h/source/meal_planner_app_v2
ExecStart=%h/source/meal_planner_app_v2/.venv/bin/python manage.py runserver 192.168.4.28:8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now meal-planner
```

Note: Do not set `User=` in the `[Service]` section — user-level systemd services on this host fail to spawn if `User=` is explicitly set.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key (optional, for YouTube importer) |

## Project Structure

```
meal_planner_app_v2/
├── accounts/          # User authentication and profiles
├── household/         # Household model
├── recipes/          # Recipe management, YouTube import, parsing
├── ingredients/      # Ingredient models with nutrition fields
├── instructions/     # Step-by-step instructions
├── tags/             # Recipe tagging
├── ratings/          # Star ratings
├── reviews/          # Recipe review queue
├── inventory/        # Pantry/inventory tracking
├── shopping/         # Shopping list generation
├── meal_planner_app/ # Weekly planner core (MealPlan, MealType, SideDish)
├── templates/         # HTML templates
├── media/            # User-uploaded images
├── logs/             # Application logs
├── start_meal_planner.sh
├── meal-planner.service
├── manage.py
└── requirements.txt
```

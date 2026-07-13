# MealPlanner

A weekly meal planner for households — plan meals by ISO week, import recipes from YouTube or photos, track what you have in the pantry, and auto-generate shopping lists. Optional AI assistance for weekly planning, nutrition lookup via USDA FoodData Central, and an in-app review queue so every imported recipe is verified before it reaches the planner.

```
        MON        TUE        WED        THU        FRI        SAT        SUN
     ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
BRK  │ Overnight│ Yogurt  │ Toast & │ Smoothie│ Avocado │ Pancakes│ Omelette│
     │ Oats     │ Parfait │ Eggs    │ Bowl    │ Toast   │ w/bacon │         │
LCH  │ Leftover│ Chicken │ Tacos   │ Pasta   │ Salad   │ Pizza   │ BBQ     │
     │ Pasta    │ Wrap    │         │         │         │ Night   │ Chicken │
DNR  │ Salmon   │ Stir    │ Meat    │ Burgers │ Thai    │ Salmon  │ Roast   │
     │ & Rice   │ Fry     │ Loaf    │         │ Curry   │         │ Chicken │
     └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
```

## What's inside

| Feature | What it does |
|---------|-------------|
| **Weekly Planner** | ISO-week grid — navigate forward/back, drag-and-drop meals between slots, rate after cooking |
| **Side dishes** | Attach multiple sides (recipe links or free-form text) to any meal entry |
| **AI Meal Suggestions** | Preferences-driven weekly plan generation, with per-feature model picker and AI plan review (accept / replace one day / regenerate) |
| **Recipe Library** | Add recipes manually, import from YouTube (single or multi-recipe videos), import from a photo (camera or upload) |
| **Watch Recipe view** | Video + transcript + frame-by-frame timeline so you can jump to the moment each step is cooked |
| **Recipe nutrition** | Per-ingredient breakdown table (protein/carbs/fat/kcal) when linked to USDA FoodData Central |
| **Inventory / Pantry** | Track what you have, where it is, when it expires, what store it came from |
| **Inventory categories** | Settings page to manage custom categories, locations, and stores |
| **Barcode scanning** | Camera or manual UPC; Open Food Facts first, with UPC Item DB fallback |
| **Receipt import** | Upload a grocery receipt photo, review parsed line items, confirm to inventory |
| **Discovery ("What can I make?")** | Recipes ranked by what % of ingredients you already have, with expiring-soon urgency flags |
| **On-Hand Ideas** | Star recipes as "on-hand" for quick-inspiration filtering when the pantry is full |
| **Shopping Lists** | One-click generate from a date range; subtracts on-hand; regenerates against the latest plan |
| **Cooking queue & reconciliation** | After a meal, tick off used ingredients and write consumption back to inventory |
| **Recipe Review Queue** | All imports land here first — link each parsed ingredient to a real inventory item, then mark Ready |
| **Backup & Restore** | JSON export/import covering recipes, inventory, shopping, ratings, reviews, AI settings, watch sessions |
| **Telegram YouTube importer** | Side-car Python bot that posts a YouTube URL to Telegram and imports the recipe back to MealPlanner |
| **Household-scoped** | Recipes, plans, inventory, ratings, reviews, preferences — all isolated per household |
| **Multi-household accounts** | Pick which household to enter on sign-in / register |

## Run with Docker (Production)

```bash
# 1. Clone
git clone https://github.com/mattwilsoncp/MealPlanner.git
cd MealPlanner

# 2. Configure — edit .env
#    Set SECRET_KEY to a long random value:
#    python -c "import secrets; print(secrets.token_urlsafe(64))"
#    Set POSTGRES_PASSWORD to a strong password
#    Optionally set OPENROUTER_API_KEY and USDA_FDC_API_KEY

# 3. Build & start
docker compose up -d --build

# 4. Run migrations (first time only)
docker compose exec app python manage.py migrate

# 5. (Optional) Load existing SQLite data
#    Export: python manage.py dumpdata -o db.json
#    Import: docker compose exec app python manage.py loaddata db.json

# → http://localhost:8000
```

To stop: `docker compose down`
To see logs: `docker compose logs -f app`
To update: `docker compose up -d --build`

---

## Run Locally (Development)

```bash
# 1. Clone & set up
git clone https://github.com/mattwilsoncp/MealPlanner.git
cd MealPlanner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# 2. Run
./start_meal_planner.sh
# → http://127.0.0.1:8000
```

Or with systemd (user-level, no `User=` line needed):

```bash
systemctl --user enable --now meal-planner
```

### CLI importers

Beyond the web UI, these CLI utilities are available:

```bash
# Import a YouTube recipe directly from the command line
python youtube_importer.py "https://www.youtube.com/watch?v=VIDEO_ID" --household-id 1

# Generate a markdown summary of any YouTube video
python youtube_importer.py "URL" --summarize -o summary.md

# Run the Telegram YouTube bot (requires TELEGRAM_BOT_TOKEN)
python telegram_youtube_recipe_importer.py
```

## Key URLs

| URL | What it is |
|-----|-----------|
| `/` | Planner home — current week's meal grid |
| `/planner/<year>/<week>/` | Any ISO week directly |
| `/recipes/` | Recipe library |
| `/recipes/import/` | Web YouTube URL importer |
| `/recipes/image-import/` | Web photo / camera importer |
| `/recipes/<id>/watch/` | Watch Recipe view — video + transcript + segmented frames |
| `/inventory/` | Pantry list |
| `/inventory/barcode/` | Barcode scanner (camera or manual) |
| `/inventory/receipt/import/` | Receipt photo upload |
| `/inventory/receipt/review/` | Review parsed receipt line items |
| `/inventory/categories/` | Manage custom inventory categories |
| `/inventory/stores/` | Manage stores + per-item price tracking |
| `/shopping/` | Shopping list generator |
| `/shopping/discovery/` | "What can I make?" ranked by inventory |
| `/cooking/` | Cooking queue — reconcile cooked meals back to inventory |
| `/on-hand/` | Recipes you've starred as "make-with-what-I-have" |
| `/reviews/queue/` | Pending imports awaiting ingredient reconciliation |
| `/preferences/` | Meal preferences (meals/week, prep time, dietary style, cuisines) |
| `/tools/ai-models/` | Per-feature AI model picker + per-household OpenRouter/USDA keys |
| `/tools/backup/` | Backup & restore (JSON) |
| `/tools/upc-usage/` | UPC lookup budget monitor |
| `/accounts/login/`, `/accounts/register/` | Auth |
| `/admin/` | Django admin (superuser only) |

## Tech Stack

- **Django 6.0** — Python 3, custom user model (no allauth)
- **PostgreSQL** — via `DATABASE_URL` env var (Docker: `docker-compose.yml`)
- **OpenRouter** — single gateway for every AI feature (recipe import text, recipe import image, receipt enrichment, AI meal planning); `/tools/ai-models/` lets each household pick the model per feature
- **USDA FoodData Central** — public nutrition database used to back-fill protein/carbs/fat on recipe ingredients; per-household key with rate-limited `DEMO_KEY` fallback
- **Open Food Facts** — primary UPC/EAN lookup on barcode scans and receipt imports
- **UPC Item DB** — fallback lookup when Open Food Facts returns nothing
- **YouTube Data API v3** — video metadata (title/description/thumb) when an API key is configured
- **youtube-transcript-api** + **markitdown** — caption retrieval with a page-metadata fallback
- **Django sessions + custom backend** — email or username login, in-app password reset
- **Gunicorn** — production server (3 workers, 2 threads)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (production) | Django secret key — never commit. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | No | Postgres URL; falls back to local SQLite (`db.sqlite3`) |
| `POSTGRES_PASSWORD` | Docker | Postgres password used by `docker-compose.yml` |
| `DEBUG` | No | `True` for local dev (default), `False` for production |
| `ALLOWED_HOSTS` | No | Comma-separated host list (default: `localhost,127.0.0.1`) |
| `YOUTUBE_API_KEY` | No | Enables YouTube Data API metadata lookup |
| `OPENROUTER_API_KEY` | No | Per-household override available at `/tools/ai-models/` |
| `USDA_FDC_API_KEY` | No | Defaults to public `DEMO_KEY`; per-household override available |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Production | SMTP creds for password reset emails; dev falls back to a `logs/` writer |

## Apps

```
accounts          — CustomUser with email+username login + multi-household picker
household         — Household model (join table for shared data)
recipes           — Recipe CRUD, YouTube import, image import, watch view
ingredients       — Ingredient definitions, unit conversion, USDA nutrition link
instructions      — Step-by-step recipe instructions
tags              — Tag recipes
ratings           — Per-recipe star rating (1–5)
reviews           — needs_review queue gate for meal planning
inventory         — Pantry: items, categories, locations, stores, UPC & receipt imports
shopping          — Shopping list generation + discovery view + on-hand
meal_planner_app  — MealPlan, MealType, SideDish, AI plan + review, watch sessions
```

## Project Structure

```
MealPlanner/
├── accounts/
├── household/
├── recipes/              ← YouTube + image importers, watch view, transcript log
├── ingredients/          ← Ingredient models, USDA linking, unit conversion
├── instructions/
├── tags/
├── ratings/
├── reviews/              ← Recipe review queue
├── inventory/            ← Pantry, categories, stores, barcode scanner, receipt import
├── shopping/             ← Shopping list, discovery, on-hand ideas
├── meal_planner_app/     ← MealPlan, SideDish, AI plan + review, preferences
├── meal_planner/         ← URL routing, WSGI, settings
├── templates/            ← base.html + app template dirs
├── docs/                 ← user_manual.md + screenshots/
├── media/                ← Uploaded recipe photos
├── logs/                 ← App logs + transcripts
├── youtube_importer.py   ← CLI YouTube + summary tool
├── telegram_youtube_recipe_importer.py  ← Telegram bot
├── scripts/qa_seed_data.py              ← QA fixtures
├── start_meal_planner.sh
├── meal-planner.service
├── manage.py
├── requirements.txt
└── DESIGN.md
```

## Tests

Suite overview at [`TEST_GUIDE.md`](./TEST_GUIDE.md). One-shot run:

```bash
./.venv/bin/python -m pytest --ds=meal_planner.settings
```

## Design

Editorial monochrome aesthetic — light-neutral surface scale, hairline borders, wide-tracked geometric display type, no shadows. Full system reference lives in [`DESIGN.md`](./DESIGN.md).

## License

MIT — built for personal use, shared freely.

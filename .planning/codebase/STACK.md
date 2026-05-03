# Tech Stack

**Focus:** tech  
**Mapped:** 2026-05-03  
**last_mapped_commit:** -

## Languages & Runtimes

| Language | Version | Notes |
|----------|---------|-------|
| Python | 3.12+ | Primary runtime |
| HTML/CSS | 5 / 3 | Templates |
| JavaScript | ES6+ | Alpine.js enhancement |

## Backend Framework

| Component | Version | Notes |
|-----------|---------|-------|
| Django | 6.0.3 | Core web framework |
| asgiref | 3.11.1 | Async support |
| psycopg | 3.0+ | PostgreSQL adapter |

**Django Apps (INSTALLED_APPS):**
- `accounts` — Custom user authentication
- `household` — Household/member management
- `recipes` — Recipe management
- `ingredients` — Ingredient catalog
- `instructions` — Recipe instructions
- `tags` — Tagging system
- `ratings` — Rating system
- `inventory` — Inventory tracking
- `reviews` — Review system
- `meal_planner_app` — Core meal planning views
- `shopping` — Shopping list generation

## Database

| Environment | Engine | Config |
|-------------|--------|--------|
| Development | SQLite | `db.sqlite3` (gitignored) |
| Production | PostgreSQL 14+ | `psycopg[binary]` driver |

**Current:** SQLite (development)

## Frontend Stack

| Component | Source | Notes |
|-----------|--------|-------|
| Tailwind CSS | CDN (v3.x) | Utility-first CSS |
| DaisyUI | CDN (v5.x) | Tailwind component library |
| Alpine.js | CDN | JS reactivity, selective enhancement |
| DM Sans | Google Fonts | Primary typography |
| JetBrains Mono | Google Fonts | Monospace (code/values) |

**No build step** — all CSS/JS loaded via CDN in `templates/base.html`.

## External APIs & Services

| Service | Package | Purpose |
|---------|---------|---------|
| YouTube Data API v3 | `google-api-python-client` | Video metadata search |
| YouTube Transcripts | `youtube-transcript-api` | Caption extraction |
| OpenAI API | `openai` | Recipe parsing/summarization (future) |

## Key Dependencies

### Core
- `Django >= 6.0`
- `psycopg[binary] >= 3.0` — PostgreSQL
- `requests >= 2.28` — HTTP client

### Media
- `Pillow >= 10.0` — Image processing
- `python-magic` — File type detection

### YouTube Integration
- `google-api-python-client >= 2.194`
- `youtube-transcript-api >= 1.2`
- `markitdown[youtube-transcription]` — Markdown from video content

### AI (v1.1)
- `openai >= 1.0` — GPT integration for recipe parsing

### Testing
- `pytest` — Test runner
- `pytest-django` — Django test integration
- `pytest-cov` — Coverage reports

## Environment & Configuration

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `meal_planner/settings.py` | Django settings |
| `manage.py` | Django CLI |
| `.venv/` | Virtual environment |
| `db.sqlite3` | Development database |

**Environment Variables (from settings.py):**
- `YOUTUBE_API_KEY` — YouTube Data API key
- `SECRET_KEY` — Django secret key
- `OPENAI_API_KEY` — OpenAI API key (future)

## System Service

**User-level systemd service:** `meal-planner.service`
- Serves at `192.168.4.28:8000`
- Uses `start_meal_planner.sh` launcher
- Note: Do NOT set `User=` in service file — causes GROUP spawn failure on this host

## Development Tools

| Tool | Purpose |
|------|---------|
| `ruff` | Linting (`.ruff_cache/`) |
| `pytest` | Testing |
| `django-admin` | Project management |
| `manage.py` | App management |

## Runtime Notes

- **DEBUG = True** in settings (development)
- **ALLOWED_HOSTS = ["*"]** (development)
- **Custom User Model:** `accounts.User` (username + email auth)
- **Auth Backend:** `accounts.backends.UsernameOrEmailBackend`

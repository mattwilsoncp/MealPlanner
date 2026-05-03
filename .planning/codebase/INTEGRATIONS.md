# External Integrations

**Focus:** tech  
**Mapped:** 2026-05-03  
**last_mapped_commit:** -

## YouTube Integration

### YouTube Data API v3

**Purpose:** Search YouTube for recipe videos, fetch video metadata (title, description, thumbnail, duration).

**Configuration:**
```python
# meal_planner/settings.py
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
```

**Package:** `google-api-python-client >= 2.194`

**Usage in codebase:**
- `recipes/youtube.py` — YouTube video search and metadata
- `youtube_importer.py` — Top-level YouTube import script

### YouTube Transcript API

**Purpose:** Extract captions/transcripts from YouTube videos for recipe content extraction.

**Package:** `youtube-transcript-api >= 1.2`

**Usage:**
- Transcript extraction for recipe instructions parsing
- Fallback when captions unavailable

### MarkitDown (YouTube)

**Purpose:** Convert YouTube video content (transcripts + metadata) to markdown.

**Package:** `markitdown[youtube-transcription]`

## OpenAI API

**Purpose:** GPT-powered recipe parsing, ingredient extraction, and content generation (v1.1 feature).

**Configuration:**
```python
# Environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
```

**Package:** `openai >= 1.0`

**Status:** Planned for v1.1 YouTube Recipe Import feature

## Database

### PostgreSQL (Production)

**Purpose:** Primary relational database for production deployment.

**Driver:** `psycopg[binary] >= 3.0`

**Configuration:**
```python
# meal_planner/settings.py (production)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "meal_planner",
        "USER": "...",
        "PASSWORD": "...",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

**Current:** SQLite in development (`db.sqlite3`)

## Authentication

### Custom User Model

**Model:** `accounts.User`

**Features:**
- Username + email authentication
- Custom backend: `accounts.backends.UsernameOrEmailBackend`

**Auth Backends:**
```python
AUTHENTICATION_BACKENDS = [
    "accounts.backends.UsernameOrEmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]
```

### Session Management

- Django session middleware (default)
- LOGIN_REDIRECT_URL = "/"
- LOGOUT_REDIRECT_URL = "/accounts/login/"

## Static & Media Files

### Static Files (CSS/JS)

- Served via Django `staticfiles`
- `STATIC_URL = "static/"`
- No local collect — all via CDN

### Media Files (Uploads)

- User-uploaded images
- `MEDIA_URL = "media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`
- Debug static serving enabled in development

## External CDN Dependencies

| Resource | CDN | Purpose |
|----------|-----|---------|
| Tailwind CSS | cdn.tailwindcss.com | Styling |
| DaisyUI | (via Tailwind CDN) | Component classes |
| Alpine.js | CDN | Reactive JavaScript |
| Google Fonts | fonts.googleapis.com | DM Sans, JetBrains Mono |

## External Data Sources

### UPC/Barcode Lookup (v1.1 planning)

**Status:** Research phase — may integrate:
- Open Food Facts API
- Local UPC database fallback

## API Endpoints (Internal)

All Django-based REST-like endpoints under:
- `/recipes/api/` — Recipe CRUD
- `/inventory/api/` — Inventory operations
- `/shopping/` — Shopping list views
- `/accounts/` — Authentication

## Third-Party Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | 2.32.3 | HTTP client |
| `Pillow` | 11.3.0 | Image handling |
| `python-magic` | 0.4.27 | File type detection |
| `beautifulsoup4` | 4.13.4 | HTML parsing |
| `lxml` | 6.0.1 | XML/HTML processing |
| `markdown-it-py` | 3.0.0 | Markdown parsing |
| `linkify-it-py` | 2.0.3 | URL detection |

## Environment Configuration

**No `.env` file in repo** — secrets loaded from environment variables:

| Variable | Used In | Notes |
|----------|---------|-------|
| `YOUTUBE_API_KEY` | `settings.py`, `youtube_importer.py` | YouTube Data API |
| `OPENAI_API_KEY` | Planned | OpenAI GPT API |
| `SECRET_KEY` | `settings.py` | Django secret key |

## Integration Architecture

```
YouTube Video URL
       │
       ▼
┌─────────────────┐     ┌──────────────────┐
│ youtube.py      │────▶│ YouTube Data API │
│ (search, meta)  │     └──────────────────┘
└─────────────────┘
       │
       ▼
┌─────────────────┐     ┌──────────────────────┐
│ youtube_transcript│────▶│ Transcript API      │
│ _api            │     └──────────────────────┘
└─────────────────┘
       │
       ▼
┌─────────────────┐     ┌──────────────────┐
│ markitdown      │────▶│ Recipe Markdown  │
└─────────────────┘     └──────────────────┘
       │
       ▼
┌─────────────────┐     ┌──────────────────┐
│ parsing.py      │────▶│ OpenAI API       │
│ (planned)       │     │ (v1.1)          │
└─────────────────┘     └──────────────────┘
```

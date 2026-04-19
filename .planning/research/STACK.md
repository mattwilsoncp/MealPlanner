# Technology Stack

**Project:** Meal Planner App v2
**Researched:** 2026-04-19
**Confidence:** HIGH

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django | 6.0.3 | Web framework | Latest production release (2026-04). Django 5.2 LTS is also solid (support until 2028), but 6.0 has latest features. Supports Python 3.10-3.14. |
| Python | 3.12+ | Runtime | Django 5.2+ officially supports 3.14. Python 3.12 is the current stable choice with best library compatibility. |

### Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 14+ | Database | Django 5.2+ dropped support for PostgreSQL 13. Version 14+ required. 16 or 17 recommended for latest features. |
| psycopg | 3.1+ | DB adapter | Use `psycopg[binary,pool]` — psycopg3 is the modern standard. psycopg2 is not receiving new features. Django 4.2+ has native psycopg3 support with built-in connection pooling. |

### Frontend
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tailwind CSS | 4.x | Styling | Current major version. User-specified. Use `@import "tailwindcss"` syntax for v4. |
| DaisyUI | 5.x | Component library | Plugin for Tailwind. User-specified. Provides 65+ pre-built components. Install via `@plugin "daisyui"` in CSS. |
| Alpine.js | 3.x | Lightweight reactivity | Only for selective enhancement (modals, dropdowns, toggles). User preference for server-rendered templates + minimal JS. |

### Authentication & Sessions
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django auth | Built-in | User authentication | User-specified. Full-featured, secure, integrates with Django ORM. |
| Django sessions | Built-in | Session management | User-specified. Cookie-based sessions for auth state. |
| Django messages | Built-in | Flash messages | User-specified. Feedback after form submissions. |

### Media Storage
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django media uploads | Built-in | Recipe photos | User-specified. Use `MEDIA_ROOT` and `MEDIA_URL` settings. |

### Development Tools
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| django-debug-toolbar | 5.x | Debugging | Essential for DB query optimization during dev. Shows query count per request. |
| django-extensions | 3.x | Dev helpers | `shell_plus`, `show_urls`, `graph_models` — speeds development. |

## Installation

```bash
# Core dependencies
pip install Django==6.0.3 "psycopg[binary,pool]">=3.1

# Production server
pip install gunicorn

# Development tools
pip install django-debug-toolbar django-extensions

# Frontend (in project static/ or via npm)
npm install -D tailwindcss daisyui alpinejs
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| DB Adapter | psycopg 3 | psycopg 2 | psycopg2 is not receiving new features. psycopg3 has native connection pooling, async support,Python 3.10+ features. |
| API Layer | None (server-rendered) | Django REST Framework | User preference for server-rendered templates. DRF adds complexity not needed for this use case. Would introduce if/when multi-user API needed. |
| JS Framework | Alpine.js (minimal) | React/Vue | User preference for "selective JS enhancement". Full SPA framework adds unnecessary complexity. |
| CSS Framework | Tailwind + DaisyUI | Bootstrap 5 | User-specified. DaisyUI provides Tailwind components without JS bloat. |
| Task Queue | None needed initially | Celery | No async/background tasks in v1 scope. Add if needed for email, exports, etc. |
| Caching | None initially | Redis | Simple app scope. Add if query performance requires. |

## Environment Configuration

```python
# settings.py key additions

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "meal_planner",
        "USER": "db_user",
        "PASSWORD": "db_password",
        "HOST": "localhost",
        "PORT": "5432",
        "OPTIONS": {
            "pool": True,  # Enable psycopg3 connection pooling
            "min_size": 2,
            "max_size": 10,
        },
    }
}

# Media files for recipe photos
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Tailwind in Django (django-tailwind npm or django-compressor)
# Or use standalone Tailwind CLI for building CSS
```

## Sources

- Django 6.0.3 release (2026): https://www.djangoproject.com/download
- Django 5.2 release notes: https://docs.djangoproject.com/en/6.0/releases/5.2/
- psycopg 3.3 release (2025): https://www.psycopg.org/articles/2025/12/01/psycopg-33-released/
- psycopg3 Django upgrade guide: https://dev.to/jimmyyeung/upgrade-to-django-5-with-psycopg3-4e8b
- Tailwind CSS + DaisyUI 5: https://v5.daisyui.com/docs/install
- Django REST Framework 3.17 requirements: https://www.django-rest-framework.org/
- Tandoor Recipes (reference): https://github.com/TandoorRecipes/recipes (8K stars, active Django recipe app)
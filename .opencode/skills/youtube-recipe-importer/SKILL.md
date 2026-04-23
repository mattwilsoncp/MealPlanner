---
name: youtube-recipe-importer
description: Parse recipe data from YouTube URLs and insert into the database
parameters:
  required:
    - youtube_url
  optional:
    - household_id
---

# youtube-recipe-importer

Import recipes from YouTube cooking videos. Fetches video metadata, parses ingredients and instructions from transcript/description, and inserts into the SQLite database with needs_review=True.

## Usage

```python
from opencode.skills.youtube_recipe_importer import import_youtube_recipe

# Parse and insert a recipe
result = import_youtube_recipe("https://www.youtube.com/watch?v=VIDEO_ID")

# Or use the load_skill function
from opencode.skills import load_skill
skill = load_skill("youtube-recipe-importer")
result = skill(youtube_url="https://www.youtube.com/watch?v=VIDEO_ID")
```

## Prerequisites

Required packages (install via pip):
```bash
pip install google-api-python-client markitdown
```

Required environment variable:
```bash
export YOUTUBE_API_KEY="your-google-api-key"
```

## How It Works

1. Extracts video ID from YouTube URL
2. Fetches video metadata using YouTube Data API v3
3. Attempts to fetch transcript using markitdown (falls back to description if unavailable)
4. Parses ingredients and instructions using pattern matching
5. Creates Recipe, Ingredient, and Instruction records in database
6. Sets needs_review=True for manual verification

## Return Value

Returns a dict with:
- `success`: bool - Whether import succeeded
- `recipe_id`: int - ID of created recipe
- `title`: str - Recipe title
- `ingredients_count`: int - Number of ingredients imported
- `instructions_count`: int - Number of instructions imported
- `error`: str - Error message if failed
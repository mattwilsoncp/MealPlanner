# Phase 1: YouTube Import - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 (first phase of v1.1): User can paste a YouTube URL into a dedicated import page, initiate import with a loading indicator, and receive clear error messaging for failed fetches.

What this phase delivers:
- Dedicated import page with URL input field
- URL validation (basic pattern check)
- Loading state feedback (spinner)
- Error handling for failed fetches
</domain>

<decisions>
## Implementation Decisions

### Import Location
- **D-01:** Dedicated import page (not inline in recipe form) — User requested a separate "Import Recipe" page for URL pasting, giving users a clean focused experience for the import flow.

### URL Validation
- **D-02:** Allow any URL, let API fail naturally — User chose to accept URLs without strict validation and handle errors from the API call. This is simpler and handles edge cases gracefully.

### Loading UI
- **D-03:** Spinner button — Button shows loading spinner while fetching. Simple, clear feedback without additional UI complexity.

### Import Page Details
- **D-04:** Import page routes to `/recipes/import/` — Standard Django view with form
- **D-05:** On success, redirect to recipe form pre-populated with YouTube data (handled in later phases)
- **D-06:** Error messages display inline on the import page

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/PROJECT.md` — Project vision and current milestone context
- `.planning/REQUIREMENTS.md` — Requirements IMP-01 through IMP-04 (Phase 1 scope)
- `.planning/v1.1-ROADMAP.md` — Phase 1 details and success criteria

### Existing Code
- `recipes/forms.py` — RecipeForm structure (for pre-population in later phase)
- `templates/recipes/recipe_form.html` — Existing recipe form UI (reference for styling consistency)

### No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- RecipeForm: ModelForm with fields for title, description, photo, video_url — can be extended or reused
- Dark theme styling: `.input-dark`, `.btn-pill` classes exist in base.html

### Established Patterns
- Server-rendered templates with Django views
- JSON API endpoints for AJAX (see recipes/api.py)
- Form handling with inline formsets for ingredients/instructions

### Integration Points
- New import view routes to `recipes/urls.py`
- On success: redirect to recipe create with import data as initial form values
- Error handling: inline messages using Django messages framework

</code_context>

<specifics>
## Specific Ideas

- Import page should feel like a focused "wizard" — clean, minimal UI
- Error states: When fetch fails, show the API error message on the page so user understands what happened
- Loading: Button shows "Importing..." text with spinner while processing

</specifics>

<deferred>
## Deferred Ideas

### From Discussion
- Integration with other recipe sites (Allrecipes, NYT) — noted for future milestone

### Not in This Phase
- Pre-populating recipe form (Phase 4 scope)
- Ingredient/instruction parsing (Phase 3 scope)
- Full form editing UI (Phase 4 scope)

</deferred>

---

*Phase: 01-youtube-import*
*Context gathered: 2026-04-22*
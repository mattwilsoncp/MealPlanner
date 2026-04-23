# Phase 3: Content Parsing - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3: Parse ingredients and instructions from the YouTube video description using NLP/entity recognition. The parsed content is pre-populated in the recipe form where users can edit/delete before saving.

What this phase delivers:
- NLP-based ingredient parsing from description text
- Instruction parsing from description or timestamps
- Pre-populated form rows with parsed content
- User can edit/delete any parsed item before saving
- Unparseable content noted for manual entry
</domain>

<decisions>
## Implementation Decisions

### Parsing Approach
- **D-07:** Use rule-based parsing with common patterns — User chose to use regex patterns and heuristics to parse ingredients and instructions from typical YouTube recipe description formats. This is simpler than full NLP and handles 80% of cases.

### Parsing Location
- **D-08:** Create dedicated parsing service — Parsing logic will be in recipes/parsing.py to keep it separate from views.

### User Editing
- **D-09:** Editable form rows pre-populated — Users can directly edit parsed ingredients/instructions in the form before saving. No separate review step.

### Unparseable Content
- **D-10:** Display in "unparsed" section — Content that can't be parsed will be shown in a textarea for manual copying, rather than trying to force-fit it.

### Phase Flow
- **D-11:** Phase 3 integrates with Phase 2 — After Phase 2 fetches description, Phase 3 parses it and passes to Phase 4 form population.
- **D-12:** Session stores parsed data — Parsed ingredients and instructions stored in session['youtube_import'] along with metadata.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project
- `.planning/v1.1-ROADMAP.md` — Phase 3 details and success criteria
- `.planning/REQUIREMENTS.md` — Requirements IMP-08 through IMP-15 (Phase 3 scope)

### Existing Code
- `recipes/youtube.py` — YouTubeService (Phase 2 output) - provides video description
- `recipes/forms.py` — RecipeForm, IngredientLinkForm, InstructionForm (for pre-population)
- `recipes/views.py` — RecipeImportView pattern for session handling

### No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### YouTube Data Flow
- Phase 2 stores in session['youtube_import']:
  ```python
  {
      'video_id': ...,
      'title': ...,
      'description': ...,
      'thumbnail_url': ...,
  }
  ```

### Existing Recipe Form Structure
- RecipeForm: ModelForm with title, description, photo, video_url
- IngredientLinkFormSet: Dynamic formset for ingredients
- InstructionFormSet: Dynamic formset for instructions
- Both formsets support extra rows and deletion

### Established Patterns
- Service classes in recipes/ (e.g., youtube.py)
- Session-based data passing between views
- Form pre-population via initial data

</code_context>

<specifics>
## Specific Ideas

### Common YouTube Recipe Description Patterns
- "Ingredients:" followed by bullet points
- Numbered instructions (1., 2., 3.)
- "Instructions:" or "Directions:" section headers
- Timestamps (0:00, 1:30, etc.) for video chapters

### Parsing Strategy
- First try to find structured sections (Ingredients:, Instructions:)
- If not found, parse line-by-line looking for quantities and action verbs
- Store unparseable lines separately for manual review

</specifics>

<deferred>
## Deferred Ideas

### From Discussion
- Integration with NLP API (e.g., Claude, GPT) — noted for future milestone
- Transcript parsing from YouTube captions — requires API key, out of scope for v1.1

### Not in This Phase
- Form population UI (Phase 4 scope)
- Photo handling (Phase 4 scope)
- Saving to database (Phase 4 scope)

</deferred>

---

*Phase: 03-content-parsing*
*Context gathered: 2026-04-22*

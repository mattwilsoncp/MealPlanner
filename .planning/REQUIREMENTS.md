# v1.1 Requirements — YouTube Recipe Import

## Active Requirements

### IMP-01: YouTube URL Import
- [ ] **IMP-01**: User can paste a YouTube video URL into a field and initiate import
- [ ] **IMP-02**: YouTube URL is validated before processing (must be valid youtube.com or youtu.be URL)
- [ ] **IMP-03**: Import shows loading state while fetching video data
- [ ] **IMP-04**: Invalid URL shows clear error message

### IMP-02: Metadata Fetch
- [ ] **IMP-05**: Video title is fetched and pre-populated in recipe form
- [ ] **IMP-06**: Video description is fetched and used for parsing
- [ ] **IMP-07**: Thumbnail URL is captured for recipe photo

### IMP-03: Ingredient Parsing
- [ ] **IMP-08**: Ingredients are parsed from video description using NLP/entity recognition
- [ ] **IMP-09**: Parsed ingredients are pre-populated in ingredient form rows
- [ ] **IMP-10**: User can edit/delete parsed ingredients before saving
- [ ] **IMP-11**: Unparseable ingredients are noted for user to add manually

### IMP-04: Instruction Parsing
- [ ] **IMP-12**: Instructions/steps are parsed from description or timestamps
- [ ] **IMP-13**: Parsed instructions are pre-populated in instruction form rows
- [ ] **IMP-14**: User can edit/delete parsed instructions before saving
- [ ] **IMP-15**: User can add additional steps manually

### IMP-05: Pre-populated Form
- [ ] **IMP-16**: Recipe form is opened pre-filled with imported data
- [ ] **IMP-17**: User can modify any field before saving recipe
- [ ] **IMP-18**: User can add photo if none was imported (user upload)

### IMP-06: Photo Handling
- [ ] **IMP-19**: YouTube thumbnail is used as default recipe photo
- [ ] **IMP-20**: User can replace thumbnail with their own uploaded photo
- [ ] **IMP-21**: User can remove photo entirely if desired

---

## Future Requirements

These are out of scope for v1.1 but noted for future milestones:

- URL import from other recipe sites (Allrecipes, NYT Cooking, etc.)
- Bulk import (multiple URLs at once)
- Import history/duplicate detection
- Collaborative household import sharing
- Import from PDF recipe files

---

## Out of Scope

Explicitly excluded from v1.1:

- **Other recipe sites**: Only YouTube for v1.1 (simpler validation)
- **Video transcript parsing**: Requires YouTube API key for captions; use description only for v1.1
- **Batch import**: Single URL at a time in v1.1
- **OCR from video frames**: Too complex for initial release

---

## Traceability

| Requirement | Phase | Status |
|--------------|-------|--------|
| IMP-01 | Phase 1 | Pending |
| IMP-02 | Phase 1 | Pending |
| IMP-03 | Phase 1 | Pending |
| IMP-04 | Phase 1 | Pending |
| IMP-05 | Phase 2 | Pending |
| IMP-06 | Phase 2 | Pending |
| IMP-07 | Phase 2 | Pending |
| IMP-08 | Phase 3 | Pending |
| IMP-09 | Phase 3 | Pending |
| IMP-10 | Phase 3 | Pending |
| IMP-11 | Phase 3 | Pending |
| IMP-12 | Phase 3 | Pending |
| IMP-13 | Phase 3 | Pending |
| IMP-14 | Phase 3 | Pending |
| IMP-15 | Phase 3 | Pending |
| IMP-16 | Phase 4 | Pending |
| IMP-17 | Phase 4 | Pending |
| IMP-18 | Phase 4 | Pending |
| IMP-19 | Phase 4 | Pending |
| IMP-20 | Phase 4 | Pending |
| IMP-21 | Phase 4 | Pending |
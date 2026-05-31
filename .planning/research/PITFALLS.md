# Pitfalls Research: AI Meal Suggestions

## API Integration Pitfalls

### 1. API Rate Limiting
- **Risk:** opencode.ai free API may rate-limit aggressive requests
- **Prevention:** Implement exponential backoff, max 1-2 requests per user action
- **Verification:** Test with concurrent requests from multiple households
- **Phase:** 2

### 2. API Downtime / Service Changes
- **Risk:** opencode.ai could change API format, deprecate free models, or go down
- **Prevention:** Abstract API call behind a service class with try/except; show graceful error message to user
- **Phase:** 2

### 3. No API Key / Authentication May Change
- **Risk:** Currently no auth is needed; this may change
- **Prevention:** Design the service class to accept a configurable API key from Django settings
- **Phase:** 2

## Prompt Engineering Pitfalls

### 4. JSON Output Parsing Failures
- **Risk:** AI may output malformed JSON, wrap in markdown code blocks, or omit fields
- **Prevention:** Use `response_format: { type: "json_object" }` if available; always wrap parsing in try/except with fallback
- **Phase:** 2

### 5. Hallucinated Ingredients
- **Risk:** AI may invent ingredients that don't exist or have unrealistic quantities
- **Prevention:** Don't auto-add AI ingredients to inventory; only use them for the meal plan display
- **Phase:** 3

### 6. Repetitive or Boring Suggestions
- **Risk:** AI may suggest similar meals across days (chicken + rice every day)
- **Prevention:** Prompt explicitly asks for variety; add constraint to avoid repeating ingredients/proteins
- **Phase:** 2

### 7. Unrealistic Cooking Times
- **Risk:** AI may claim "15-minute meals" that actually take an hour
- **Prevention:** Present cook times as estimates; don't lock users into tight schedules
- **Phase:** 3

## UX Pitfalls

### 8. User Abandons Mid-Generation
- **Risk:** User clicks generate, leaves the page, AI response is lost
- **Prevention:** Store AI session results so user can return; or use a notification pattern
- **Phase:** 3

### 9. Generated Meals Don't Match Preferences
- **Risk:** AI ignores dietary restrictions (generates non-vegan meals for vegan users)
- **Prevention:** Validate dietary restrictions in the prompt AND the output; warn user if constraint violated
- **Phase:** 3

### 10. Overwriting Existing Meal Plan
- **Risk:** User has already planned some days; AI generation may conflict
- **Prevention:** AI plan should only suggest for empty slots, or use a separate "AI suggestions" layer that doesn't modify existing data until user accepts
- **Phase:** 3

### 11. Inventory Data Privacy
- **Risk:** Sending full inventory data to external API
- **Prevention:** Only send ingredient names and quantities (no user PII); document what's sent
- **Phase:** 2

## Integration Pitfalls

### 12. Existing Planner Constraints
- **Risk:** The existing planner has unique constraints (household, date, meal_type, recipe) that may conflict with AI suggestions
- **Prevention:** Ensure AI plan accepts use the same model; handle constraint violations gracefully
- **Phase:** 4

### 13. Missing Ingredient Calculation
- **Risk:** Shopping list may duplicate existing inventory items or miss AI-ingredient needs
- **Prevention:** Reuse existing shopping list generation logic; map AI ingredient names to your ingredient model
- **Phase:** 4

## Performance Pitfalls

### 14. Slow API Response
- **Risk:** Meal plan generation may take 10-20 seconds for a full week
- **Prevention:** Show loading spinner with progress messages; consider streaming the response
- **Phase:** 2

### 15. Many Concurrent Requests
- **Risk:** Multiple households triggering generation simultaneously
- **Prevention:** Implement per-household rate limiting (max 1 generation per 30 seconds)
- **Phase:** 2

## Summary of Critical Risks

| Risk | Severity | Prevention | Phase |
|------|----------|------------|-------|
| API rate limiting | Medium | Retry with backoff | 2 |
| JSON parsing failure | High | `response_format: json_object` + fallback parsing | 2 |
| Repetitive suggestions | Medium | Prompt with variety constraints | 2 |
| Overwriting existing plan | High | Separate "AI suggestions" layer | 3 |
| Dietary restriction violations | High | Validate in prompt AND output | 3 |

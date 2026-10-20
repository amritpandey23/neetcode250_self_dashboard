# Active Context

## Current focus
AI Coach model picker: dropdown of Gemini models that support `generateContent`.

## Recent decisions
- Model list comes from Gemini `models.list` (filtered to `generateContent`), cached 1h in-process; fallback static list if API fails
- `GEMINI_MODEL` remains the server default; client selection is validated via `resolve_model` and persisted in localStorage
- Chat POST accepts `model` and returns the resolved model id

## Next steps
- Optional: surface linked Spaces entries in AI Coach context
- Optional: export notes / review due dates
- Soft delete / richer account settings beyond email challenge

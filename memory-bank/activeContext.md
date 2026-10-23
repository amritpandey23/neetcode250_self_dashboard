# Active Context

## Current focus
Shared question of the day: one problem for every user, emailed only to opted-in accounts, and shown on the dashboard for everyone.

## Recent decisions
- `DailyChallenge` stores one problem per server-local date; `question_of_the_day()` creates it once and reuses it
- Opted-in users still receive it at their own local send time; the problem is no longer a per-user unsolved pick
- Dashboard shows that problem (with the viewer’s own status) whether or not email is enabled
- Model list comes from Gemini `models.list` (filtered to `generateContent`), cached 1h in-process; fallback static list if API fails
- `GEMINI_MODEL` remains the server default; client selection is validated via `resolve_model` and persisted in localStorage
- Chat POST accepts `model` and returns the resolved model id

## Next steps
- Optional: surface linked Spaces entries in AI Coach context
- Optional: export notes / review due dates
- Soft delete / richer account settings beyond email challenge

# Active Context

## Current focus
Contest page: contests overlapping the user's local today are listed in a table above the month calendar.

## Recent decisions
- A contest is "happening today" when its start–end window overlaps the user's local calendar day, including contests that started earlier and are still running
- The table is hidden when nothing overlaps today, and it stays visible when the calendar is on another month
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

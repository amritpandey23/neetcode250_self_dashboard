# Active Context

## Current focus
Split overview Dashboard from Problems browser.

## Recent decisions
- Status values: `todo`, `attempted`, `done` — editable only on problem page
- Dashboard/list status shown as icon-only (label via title/aria); LeetCode icon sits beside problem name
- Dashboard overview shows top 3 aging problems with weeks since last practice
- Reset progress (`POST /problem/<slug>/reset`) clears status/notes/practice stats; keeps bookmark
- `/dashboard` = overview cards only; `/problems` = All Problems + category browser
- Contests page fetches LeetCode GraphQL `allContests` (cached 1h) for upcoming weekly/biweekly
- Favicon matches brand mark (teal + code glyph)
- Problem back link is contextual via `next` query
- Notes default to preview-only; dirty Save tracking on detail page
- Prev/next adjacent problems by `order_index`

## Next steps
- Optional: export notes
- Optional: review due dates / spaced repetition

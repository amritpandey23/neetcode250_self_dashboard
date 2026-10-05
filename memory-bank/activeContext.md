# Active Context

## Current focus
Daily random-problem email challenge: Settings page + SMTP/console delivery + daily scheduler.

## Recent decisions
- Daily cadence (default 09:00 local); test via Settings “Send test email now” (no minute spam)
- SMTP when `MAIL_SERVER` set; otherwise log full message to Flask console
- Opt-in via `User.email_challenge_enabled`; email required when enabling
- Per-user send time + IANA timezone in Settings (browser autodetect); scheduler evaluates due time in the user's zone
- Picks random **unsolved** problem (`status != done`)
- Background daemon thread started from `create_app`, guarded for Flask debug reloader
- External links in scheduled emails use `APP_BASE_URL` when no request context

## Next steps
- Optional: surface linked Spaces entries in AI Coach context
- Optional: export notes / review due dates
- Soft delete / richer account settings beyond email challenge

# Tech Context

## Stack
- Python 3
- Flask 3
- Flask-Login
- Flask-SQLAlchemy
- SQLite
- Werkzeug password hashing
- stdlib `smtplib` + background thread for daily email challenge

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Email challenge env
- Leave `MAIL_SERVER` empty → emails logged to console (good for testing via Settings)
- Set `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` for SMTP
- `EMAIL_CHALLENGE_HOUR` / `EMAIL_CHALLENGE_MINUTE` (default 9:00 local)
- `APP_BASE_URL` for in-email dashboard links from the scheduler (default `http://127.0.0.1:5001`)

## Constraints
- Single-process local use assumed
- Change `SECRET_KEY` for any non-dev deploy
- JSON source of truth for problem catalog: `neetcode_250_complete.json`

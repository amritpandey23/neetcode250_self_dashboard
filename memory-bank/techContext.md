# Tech Context

## Stack
- Python 3
- Flask 3
- Flask-Login
- Flask-SQLAlchemy
- SQLite
- Werkzeug password hashing

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Constraints
- Single-process local use assumed
- Change `SECRET_KEY` for any non-dev deploy
- JSON source of truth for problem catalog: `neetcode_250_complete.json`

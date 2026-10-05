import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "neetcode.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    NEETCODE_JSON = os.path.join(BASE_DIR, "neetcode_250_complete.json")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Email challenge — leave MAIL_SERVER empty for console/log delivery
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "neetcode250@localhost")
    EMAIL_CHALLENGE_HOUR = int(os.environ.get("EMAIL_CHALLENGE_HOUR", "9"))
    EMAIL_CHALLENGE_MINUTE = int(os.environ.get("EMAIL_CHALLENGE_MINUTE", "0"))
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5001").rstrip("/")

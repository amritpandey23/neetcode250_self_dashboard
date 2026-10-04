import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "neetcode.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    NEETCODE_JSON = os.path.join(BASE_DIR, "neetcode_250_complete.json")

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    progress_entries = db.relationship(
        "Progress", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Problem(db.Model):
    __tablename__ = "problems"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    name = db.Column(db.String(300), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    neetcode_url = db.Column(db.String(500), nullable=False)
    leetcode_url = db.Column(db.String(500), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    progress_entries = db.relationship("Progress", back_populates="problem")


class Progress(db.Model):
    __tablename__ = "progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "problem_id", name="uq_user_problem"),
    )

    STATUSES = ("todo", "attempted", "done")
    STATUS_LABELS = {
        "todo": "Todo",
        "attempted": "Attempted",
        "done": "Done",
    }

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey("problems.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="todo")
    notes = db.Column(db.Text, default="")
    bookmarked = db.Column(db.Boolean, nullable=False, default=False)
    solve_count = db.Column(db.Integer, nullable=False, default=0)
    last_practiced_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="progress_entries")
    problem = db.relationship("Problem", back_populates="progress_entries")

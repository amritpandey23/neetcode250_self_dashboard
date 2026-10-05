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
    email = db.Column(db.String(255), nullable=True)
    email_challenge_enabled = db.Column(db.Boolean, nullable=False, default=False)
    email_challenge_hour = db.Column(db.Integer, nullable=False, default=9)
    email_challenge_minute = db.Column(db.Integer, nullable=False, default=0)
    email_challenge_last_sent_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    progress_entries = db.relationship(
        "Progress", back_populates="user", cascade="all, delete-orphan"
    )
    spaces = db.relationship(
        "Space", back_populates="user", cascade="all, delete-orphan"
    )
    activity_logs = db.relationship(
        "ActivityLog",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ActivityLog.created_at.desc()",
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


class Space(db.Model):
    __tablename__ = "spaces"
    __table_args__ = (
        db.UniqueConstraint("user_id", "slug", name="uq_space_user_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, index=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="spaces")
    categories = db.relationship(
        "DocCategory",
        back_populates="space",
        cascade="all, delete-orphan",
        order_by="DocCategory.order_index",
    )


class DocCategory(db.Model):
    __tablename__ = "doc_categories"
    __table_args__ = (
        db.UniqueConstraint("space_id", "slug", name="uq_doc_category_space_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    space_id = db.Column(db.Integer, db.ForeignKey("spaces.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, index=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    space = db.relationship("Space", back_populates="categories")
    sections = db.relationship(
        "DocSection",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="DocSection.order_index",
    )
    entries = db.relationship(
        "DocEntry",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="DocEntry.order_index",
    )


class DocSection(db.Model):
    __tablename__ = "doc_sections"
    __table_args__ = (
        db.UniqueConstraint("category_id", "slug", name="uq_doc_section_category_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("doc_categories.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, index=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    category = db.relationship("DocCategory", back_populates="sections")
    entries = db.relationship(
        "DocEntry",
        back_populates="section",
        cascade="all, delete",
        order_by="DocEntry.order_index",
    )


class DocEntry(db.Model):
    __tablename__ = "doc_entries"
    __table_args__ = (
        db.UniqueConstraint("category_id", "slug", name="uq_doc_entry_category_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("doc_categories.id"), nullable=False, index=True
    )
    section_id = db.Column(
        db.Integer, db.ForeignKey("doc_sections.id"), nullable=True, index=True
    )
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(320), nullable=False, index=True)
    body = db.Column(db.Text, default="")
    order_index = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    category = db.relationship("DocCategory", back_populates="entries")
    section = db.relationship("DocSection", back_populates="entries")
    problem_links = db.relationship(
        "ProblemEntryLink",
        back_populates="entry",
        cascade="all, delete-orphan",
    )


class ProblemEntryLink(db.Model):
    """Per-user link from a problem to a Spaces document entry."""

    __tablename__ = "problem_entry_links"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "problem_id", "entry_id", name="uq_user_problem_entry_link"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    problem_id = db.Column(
        db.Integer, db.ForeignKey("problems.id"), nullable=False, index=True
    )
    entry_id = db.Column(
        db.Integer, db.ForeignKey("doc_entries.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User")
    problem = db.relationship("Problem")
    entry = db.relationship("DocEntry", back_populates="problem_links")


class ActivityLog(db.Model):
    """Per-user chronological log of core app actions."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    summary = db.Column(db.String(500), nullable=False)
    entity_type = db.Column(db.String(40), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    href = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    user = db.relationship("User", back_populates="activity_logs")

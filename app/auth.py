from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.email_challenge import send_challenge_for_user
from app.models import User

auth_bp = Blueprint("auth", __name__)


def _valid_email(value: str) -> bool:
    if not value or "@" not in value or " " in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created. Welcome!", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    mail_configured = bool((current_app.config.get("MAIL_SERVER") or "").strip())
    default_hour = int(current_app.config.get("EMAIL_CHALLENGE_HOUR", 9))
    default_minute = int(current_app.config.get("EMAIL_CHALLENGE_MINUTE", 0))

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip()

        if action == "test_email":
            email = (current_user.email or "").strip()
            if not email:
                flash("Save an email address before sending a test.", "error")
            else:
                try:
                    problem = send_challenge_for_user(current_user)
                    if problem is None:
                        flash("No unsolved problems left to email.", "info")
                    elif mail_configured:
                        flash(
                            f"Test email sent to {email} ({problem.name}).",
                            "success",
                        )
                    else:
                        flash(
                            f"Test email for {problem.name} logged to the console "
                            f"(SMTP not configured).",
                            "success",
                        )
                except Exception as exc:
                    flash(f"Failed to send test email: {exc}", "error")
            return redirect(url_for("auth.settings"))

        email = (request.form.get("email") or "").strip()
        enabled = bool(request.form.get("email_challenge_enabled"))
        time_raw = (request.form.get("email_challenge_time") or "").strip()
        hour = (
            current_user.email_challenge_hour
            if current_user.email_challenge_hour is not None
            else default_hour
        )
        minute = (
            current_user.email_challenge_minute
            if current_user.email_challenge_minute is not None
            else default_minute
        )
        time_error = None

        if time_raw:
            parts = time_raw.split(":")
            if len(parts) < 2:
                time_error = "Enter a valid send time."
            else:
                try:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if not (0 <= hour <= 23 and 0 <= minute <= 59):
                        raise ValueError
                except ValueError:
                    time_error = "Enter a valid send time (HH:MM)."

        if email and not _valid_email(email):
            flash("Enter a valid email address.", "error")
        elif enabled and not email:
            flash("Email is required to enable daily challenges.", "error")
        elif time_error:
            flash(time_error, "error")
        else:
            current_user.email = email or None
            current_user.email_challenge_enabled = enabled
            current_user.email_challenge_hour = hour
            current_user.email_challenge_minute = minute
            db.session.commit()
            if enabled:
                flash(
                    f"Settings saved. Daily challenge emails at "
                    f"{hour:02d}:{minute:02d} (server local time).",
                    "success",
                )
            else:
                flash("Settings saved.", "success")
            return redirect(url_for("auth.settings"))

    hour = (
        current_user.email_challenge_hour
        if current_user.email_challenge_hour is not None
        else default_hour
    )
    minute = (
        current_user.email_challenge_minute
        if current_user.email_challenge_minute is not None
        else default_minute
    )
    return render_template(
        "settings.html",
        mail_configured=mail_configured,
        challenge_time=f"{hour:02d}:{minute:02d}",
    )

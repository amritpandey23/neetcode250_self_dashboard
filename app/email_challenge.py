"""Daily random-problem email challenge: pick, send, and schedule."""

from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from datetime import datetime
from email.message import EmailMessage

from flask import Flask, current_app, url_for

from app import db
from app.models import Problem, Progress, User

logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()


def pick_random_unsolved(user_id: int) -> Problem | None:
    """Return a random problem the user has not marked done."""
    done_ids = db.session.query(Progress.problem_id).filter_by(
        user_id=user_id, status="done"
    )
    return (
        Problem.query.filter(~Problem.id.in_(done_ids))
        .order_by(db.func.random())
        .first()
    )


def _difficulty_color(difficulty: str) -> str:
    return {
        "Easy": "#15803d",
        "Medium": "#b45309",
        "Hard": "#b91c1c",
    }.get(difficulty, "#475569")


def _difficulty_bg(difficulty: str) -> str:
    return {
        "Easy": "#dcfce7",
        "Medium": "#fef3c7",
        "Hard": "#fee2e2",
    }.get(difficulty, "#f1f5f9")


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_plain_body(user: User, problem: Problem, app_url: str) -> str:
    return (
        f"Hi {user.username},\n\n"
        f"Your random NeetCode challenge for today:\n\n"
        f"  {problem.name}\n"
        f"  Difficulty: {problem.difficulty}\n"
        f"  Category:   {problem.category}\n\n"
        f"Open in dashboard: {app_url}\n"
        f"Solve on LeetCode:  {problem.leetcode_url}\n\n"
        f"— NeetCode 250 Self Dashboard\n"
    )


def _build_html_body(user: User, problem: Problem, app_url: str) -> str:
    name = _escape(problem.name)
    username = _escape(user.username)
    category = _escape(problem.category)
    difficulty = _escape(problem.difficulty)
    diff_color = _difficulty_color(problem.difficulty)
    diff_bg = _difficulty_bg(problem.difficulty)
    leetcode_url = _escape(problem.leetcode_url)
    dash_url = _escape(app_url)
    today = datetime.now().strftime("%A, %b %d").replace(" 0", " ")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily challenge</title>
</head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#111827;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;">
          <tr>
            <td style="padding:28px 28px 20px;background:linear-gradient(135deg,#0f766e 0%,#0b5f58 100%);">
              <p style="margin:0 0 6px;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:rgba(255,255,255,0.75);font-weight:600;">
                NeetCode 250 · Daily challenge
              </p>
              <h1 style="margin:0;font-size:22px;line-height:1.3;font-weight:700;color:#ffffff;letter-spacing:-0.02em;">
                Ready for today’s problem?
              </h1>
              <p style="margin:10px 0 0;font-size:13px;color:rgba(255,255,255,0.8);">
                {today}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">
              <p style="margin:0 0 20px;font-size:15px;line-height:1.55;color:#374151;">
                Hi <strong style="color:#111827;">{username}</strong> — here’s a random unsolved problem from your list.
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fb;border:1px solid #e5e7eb;border-radius:12px;">
                <tr>
                  <td style="padding:22px 22px 18px;">
                    <p style="margin:0 0 8px;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:#6b7280;font-weight:600;">
                      Today’s pick
                    </p>
                    <h2 style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#111827;letter-spacing:-0.02em;">
                      {name}
                    </h2>
                    <table role="presentation" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding:0 8px 0 0;">
                          <span style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:650;color:{diff_color};background:{diff_bg};">
                            {difficulty}
                          </span>
                        </td>
                        <td>
                          <span style="display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:550;color:#374151;background:#eef2f7;">
                            {category}
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                <tr>
                  <td style="padding:0 10px 10px 0;">
                    <a href="{dash_url}" style="display:inline-block;padding:12px 18px;border-radius:10px;background:#0f766e;color:#ffffff;font-size:14px;font-weight:650;text-decoration:none;">
                      Open in dashboard →
                    </a>
                  </td>
                  <td style="padding:0 0 10px 0;">
                    <a href="{leetcode_url}" style="display:inline-block;padding:12px 18px;border-radius:10px;background:#ffffff;color:#0f766e;font-size:14px;font-weight:650;text-decoration:none;border:1px solid rgba(15,118,110,0.35);">
                      Solve on LeetCode
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:22px 0 0;font-size:12.5px;line-height:1.5;color:#9ca3af;">
                You’re receiving this because daily challenge emails are enabled in Settings.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 28px;border-top:1px solid #e5e7eb;background:#fafafa;">
              <p style="margin:0;font-size:12px;color:#9ca3af;">
                NeetCode 250 Self Dashboard
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _build_message(user: User, problem: Problem, app_url: str) -> EmailMessage:
    subject = f"Daily challenge: {problem.name}"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = user.email
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or "neetcode250@localhost"
    msg["From"] = sender
    msg.set_content(_build_plain_body(user, problem, app_url))
    msg.add_alternative(_build_html_body(user, problem, app_url), subtype="html")
    return msg


def send_problem_email(user: User, problem: Problem, app_url: str | None = None) -> str:
    """
    Send (or log) a challenge email for one problem.

    Returns \"smtp\" or \"console\" indicating the delivery path used.
    """
    if not user.email:
        raise ValueError("User has no email address configured.")

    if app_url is None:
        base = (current_app.config.get("APP_BASE_URL") or "http://127.0.0.1:5001").rstrip("/")
        try:
            app_url = url_for("main.problem_detail", slug=problem.slug, _external=True)
        except RuntimeError:
            # No request context (e.g. daily scheduler thread).
            app_url = f"{base}/problem/{problem.slug}"

    msg = _build_message(user, problem, app_url)
    mail_server = (current_app.config.get("MAIL_SERVER") or "").strip()

    if not mail_server:
        plain = msg.get_body(preferencelist=("plain",))
        html = msg.get_body(preferencelist=("html",))
        logger.info(
            "EMAIL_CHALLENGE (console mode) to=%s subject=%s\n--- plain ---\n%s\n--- html (%s chars) ---\n%s",
            user.email,
            msg["Subject"],
            plain.get_content() if plain else "",
            len(html.get_content()) if html else 0,
            (html.get_content()[:500] + "…") if html and len(html.get_content()) > 500 else (html.get_content() if html else ""),
        )
        return "console"

    port = int(current_app.config.get("MAIL_PORT") or 587)
    use_tls = bool(current_app.config.get("MAIL_USE_TLS", True))
    username = current_app.config.get("MAIL_USERNAME") or ""
    password = current_app.config.get("MAIL_PASSWORD") or ""

    with smtplib.SMTP(mail_server, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(msg)

    logger.info("EMAIL_CHALLENGE sent via SMTP to=%s problem=%s", user.email, problem.slug)
    return "smtp"


def send_challenge_for_user(user: User, *, mark_sent: bool = False) -> Problem | None:
    """Pick a random unsolved problem and email it. Returns the problem or None."""
    problem = pick_random_unsolved(user.id)
    if problem is None:
        logger.info("EMAIL_CHALLENGE skip user=%s: no unsolved problems", user.username)
        return None
    send_problem_email(user, problem)
    if mark_sent:
        user.email_challenge_last_sent_on = datetime.now().date()
        db.session.commit()
    return problem


def _user_challenge_time(user: User) -> tuple[int, int]:
    hour = user.email_challenge_hour
    minute = user.email_challenge_minute
    if hour is None:
        hour = int(current_app.config.get("EMAIL_CHALLENGE_HOUR", 9))
    if minute is None:
        minute = int(current_app.config.get("EMAIL_CHALLENGE_MINUTE", 0))
    return int(hour) % 24, int(minute) % 60


def _is_challenge_due(user: User, now: datetime | None = None) -> bool:
    """True if the user should receive today's challenge at the current local time."""
    now = now or datetime.now()
    today = now.date()
    if user.email_challenge_last_sent_on == today:
        return False
    hour, minute = _user_challenge_time(user)
    preferred = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= preferred


def run_daily_challenge_for_all() -> int:
    """Send today's challenge to every opted-in user who is due. Returns emails sent."""
    now = datetime.now()
    users = User.query.filter(
        User.email_challenge_enabled.is_(True),
        User.email.isnot(None),
        User.email != "",
    ).all()
    sent = 0
    for user in users:
        if not _is_challenge_due(user, now):
            continue
        try:
            if send_challenge_for_user(user, mark_sent=True) is not None:
                sent += 1
        except Exception:
            logger.exception(
                "EMAIL_CHALLENGE failed for user=%s email=%s",
                user.username,
                user.email,
            )
    if sent:
        logger.info(
            "EMAIL_CHALLENGE due run finished: %s sent of %s opted-in",
            sent,
            len(users),
        )
    return sent


def _scheduler_loop(app: Flask) -> None:
    with app.app_context():
        logger.info(
            "EMAIL_CHALLENGE scheduler started (checks every 60s for per-user send times)"
        )
        while True:
            try:
                run_daily_challenge_for_all()
            except Exception:
                logger.exception("EMAIL_CHALLENGE due run crashed")
            time.sleep(60)


def start_email_challenge_scheduler(app: Flask) -> None:
    """Start the daily daemon thread once (safe under Flask debug reloader)."""
    global _scheduler_started

    # Flask debug reloader runs the app twice; only start in the child process.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    thread = threading.Thread(
        target=_scheduler_loop,
        args=(app,),
        name="email-challenge-scheduler",
        daemon=True,
    )
    thread.start()

"""Gemini API helper for problem-page coaching chat."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

DEFAULT_MODEL = "gemini-2.5-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_HISTORY_TURNS = 16
MAX_MESSAGE_CHARS = 8000
MAX_NOTES_CHARS = 12000


class GeminiError(Exception):
    """Raised when the Gemini API call fails."""

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _ssl_context():
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _truncate(text, limit):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_system_instruction(problem, context):
    status = (context or {}).get("status") or "todo"
    notes = _truncate((context or {}).get("notes") or "", MAX_NOTES_CHARS)
    bookmarked = bool((context or {}).get("bookmarked"))
    solve_count = (context or {}).get("solve_count")
    last_practiced = (context or {}).get("last_practiced_at") or "never"

    try:
        solve_count = int(solve_count)
    except (TypeError, ValueError):
        solve_count = 0

    return f"""You are a focused coding interview coach inside a NeetCode 250 practice tracker.

Help the learner with the current problem using Socratic guidance when they ask for hints.
Prefer clear structure, markdown, and short code snippets when useful.
Do not dump a full optimal solution unless they explicitly ask for the full solution.
If their notes already contain an approach, build on that instead of restarting from scratch.

Current problem:
- Name: {problem.name}
- Category: {problem.category}
- Difficulty: {problem.difficulty}
- LeetCode: {problem.leetcode_url}
- Slug: {problem.slug}

Learner progress (live from the page — may be unsaved):
- Status: {status}
- Bookmarked: {"yes" if bookmarked else "no"}
- Solve count: {solve_count}
- Last practiced: {last_practiced}
- Notes:
```md
{notes or "(empty)"}
```
"""


def _normalize_history(history):
    cleaned = []
    if not isinstance(history, list):
        return cleaned

    for item in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "model") or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        cleaned.append(
            {
                "role": role,
                "parts": [{"text": _truncate(content, MAX_MESSAGE_CHARS)}],
            }
        )
    return cleaned


def _extract_text(payload):
    candidates = payload.get("candidates") or []
    if not candidates:
        feedback = payload.get("promptFeedback") or {}
        block = feedback.get("blockReason")
        if block:
            raise GeminiError(f"Response blocked by Gemini ({block}).", status_code=400)
        raise GeminiError("Gemini returned no candidates.", status_code=502)

    candidate = candidates[0]
    finish = candidate.get("finishReason")
    parts = (candidate.get("content") or {}).get("parts") or []
    texts = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        # Gemini 2.5 may include thought parts; keep only visible answer text.
        if part.get("thought"):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)

    answer = "\n".join(texts).strip()
    if answer:
        return answer

    if finish and finish != "STOP":
        raise GeminiError(f"Gemini stopped early ({finish}).", status_code=502)
    raise GeminiError("Gemini returned an empty response.", status_code=502)


def chat(api_key, model, problem, message, history=None, context=None):
    """Send a chat turn to Gemini and return the assistant markdown text."""
    if not api_key:
        raise GeminiError(
            "GEMINI_API_KEY is not configured on the server.",
            status_code=503,
        )

    message = (message or "").strip()
    if not message:
        raise GeminiError("Message is required.", status_code=400)
    if len(message) > MAX_MESSAGE_CHARS:
        raise GeminiError(
            f"Message is too long (max {MAX_MESSAGE_CHARS} characters).",
            status_code=400,
        )

    model_name = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    contents = _normalize_history(history)
    contents.append(
        {
            "role": "user",
            "parts": [{"text": _truncate(message, MAX_MESSAGE_CHARS)}],
        }
    )

    body = {
        "systemInstruction": {
            "parts": [{"text": build_system_instruction(problem, context)}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }

    url = (
        f"{API_BASE}/models/{urllib.parse.quote(model_name, safe='')}:generateContent"
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, context=_ssl_context(), timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(detail)
            message_text = (
                (err_json.get("error") or {}).get("message")
                or detail
                or exc.reason
            )
        except json.JSONDecodeError:
            message_text = detail or str(exc.reason)
        raise GeminiError(
            f"Gemini API error ({exc.code}): {message_text}",
            status_code=502,
        ) from exc
    except urllib.error.URLError as exc:
        raise GeminiError(f"Could not reach Gemini API: {exc.reason}", status_code=502) from exc
    except TimeoutError as exc:
        raise GeminiError("Gemini request timed out.", status_code=504) from exc

    return _extract_text(payload)

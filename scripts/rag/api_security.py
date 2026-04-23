"""HTTP API guardrails: optional API key, input bounds, and safe error responses."""

from __future__ import annotations

import hmac
import os
from typing import Any

from flask import Request, current_app, has_request_context, jsonify

from config import RAGConfig


class UserInputError(Exception):
    """Raised when user input fails validation (length, empty, etc.)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def get_required_api_key() -> str | None:
    """If set, all state-changing / RAG /api/* routes require this key."""
    k = (os.environ.get("RAG_API_KEY") or "").strip()
    return k or None


def is_browser_key_exposure_enabled() -> bool:
    return os.environ.get("RAG_EXPOSE_KEY_TO_UI", "").strip() in ("1", "true", "yes")


def _extract_api_key_from_request(request: Request) -> str | None:
    h = request.headers.get("X-API-Key")
    if h and h.strip():
        return h.strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_session_password() -> str | None:
    """If set, browser clients can POST /api/login with this password (Flask session)."""
    p = (os.environ.get("RAG_SESSION_PASSWORD") or "").strip()
    return p or None


def auth_allows_request(request: Request, session: Any) -> tuple[bool, str | None]:
    """When RAG_API_KEY and/or RAG_SESSION_PASSWORD is set, require a valid key or logged-in session."""
    need_key = get_required_api_key()
    need_sess = get_session_password()
    if not need_key and not need_sess:
        return True, None
    if session and session.get("user_id"):
        return True, None
    if need_key:
        ok, _ = check_api_key(request)
        if ok:
            return True, None
    if need_sess and session.get("rag_ok"):
        return True, None
    if need_key or need_sess:
        return False, "Unauthorized. Send a valid X-API-Key, log in (POST /api/login), or use /auth."
    return True, None


def check_api_key(request: Request) -> tuple[bool, str | None]:
    """Returns (ok, error_message). ok True if auth not configured or key matches."""
    required = get_required_api_key()
    if not required:
        return True, None
    got = _extract_api_key_from_request(request) or ""
    if not got or len(got) != len(required):
        return False, "Invalid or missing API key. Send X-API-Key or Authorization: Bearer."
    if not hmac.compare_digest(got, required):
        return False, "Invalid or missing API key. Send X-API-Key or Authorization: Bearer."
    return True, None


def get_rate_limit_key(request: Request) -> str:
    if os.environ.get("TRUST_PROXY", "").strip() in ("1", "true", "yes"):
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip() or (request.remote_addr or "local")
    return request.remote_addr or "local"


def wrap_untrusted_user_text(text: str) -> str:
    """Mark user-supplied text so it is clearly boundary-separated from system instructions."""
    t = (text or "").strip()
    if t.startswith("<<<UNTRUSTED_USER"):
        return text if text else ""
    return f"<<<UNTRUSTED_USER\n{t}\nUNTRUSTED_USER>>>"


def validate_and_prepare_question(
    question: str,
    config: RAGConfig,
) -> str:
    q = (question or "").strip()
    if not q:
        raise UserInputError("No question provided")
    max_len = int(os.environ.get("RAG_MAX_QUESTION_LEN", str(config.max_question_len)))
    if len(q) > max_len:
        raise UserInputError(f"Question too long (max {max_len} characters)")
    return q


def load_history_into_memory(
    memory: Any,
    history: list[dict[str, Any]] | None,
    config: RAGConfig,
) -> None:
    """Fill conversation memory from client JSON; user turns are delimiter-wrapped."""
    for msg in sanitize_client_history(history, config):
        if msg["role"] == "user":
            memory.add("user", wrap_untrusted_user_text(msg["content"]))
        else:
            memory.add("assistant", msg["content"])


def sanitize_client_history(
    history: list[dict[str, Any]] | None,
    config: RAGConfig,
) -> list[dict[str, str]]:
    """Limit size and per-message length of client-supplied agent history (prompt injection / DoS)."""
    if not history:
        return []
    max_msgs = min(config.max_client_history_messages, 40)
    max_len = int(os.environ.get("RAG_MAX_MESSAGE_CONTENT_LEN", "12000"))
    out: list[dict[str, str]] = []
    for msg in history[-max_msgs:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content", ""))[:max_len]
        if content.strip():
            out.append({"role": role, "content": content})
    return out


def build_json_error(
    public_message: str,
    code: int,
    exc: Exception | None = None,
) -> tuple[Any, int]:
    """Return (jsonify(...), code). Log internal detail; never echo raw exceptions to client."""
    import logging

    log = logging.getLogger(__name__)
    if exc is not None:
        try:
            if has_request_context():
                current_app.logger.exception("Request failed: %s", public_message)
            else:
                log.exception("Request failed: %s", public_message)
        except RuntimeError:
            log.exception("Request failed: %s", public_message)
        if has_request_context() and current_app.debug:
            public_message = f"{public_message} ({type(exc).__name__})"
    return jsonify({"error": public_message}), code

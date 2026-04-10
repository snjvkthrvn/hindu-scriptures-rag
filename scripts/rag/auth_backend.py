"""Session-based auth: SQLite users + login/register/logout for Flask apps.

Enable with env AUTH_REQUIRED=1 and set FLASK_SECRET_KEY for production.
Guests can use the app without logging in until GUEST_MESSAGE_LIMIT (default 2) RAG
messages are consumed; then they must sign in. No automatic redirect to login on load.

Optional: ADMIN_EMAIL + ADMIN_PASSWORD to create the first user when the DB is empty.
Optional: OPEN_REGISTRATION=1 to allow POST /auth/register.
Optional: GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET for "Sign in with Google" (OAuth 2 / OIDC).

Logged-in users: GET/PUT /api/chat/state stores conversation JSON in SQLite (user_chats).
Guests keep using the browser only; guest RAG quota unchanged when AUTH_REQUIRED=1.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_DB_PATH = PROJECT_ROOT / "data" / "auth.db"

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def auth_required() -> bool:
    return os.environ.get("AUTH_REQUIRED", "").strip().lower() in ("1", "true", "yes")


def open_registration() -> bool:
    return os.environ.get("OPEN_REGISTRATION", "").strip().lower() in ("1", "true", "yes")


def _authlib_available() -> bool:
    try:
        import authlib  # noqa: F401
        return True
    except ImportError:
        return False


def google_oauth_configured() -> bool:
    cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    csec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    return bool(cid and csec) and _authlib_available()


def guest_message_limit() -> int:
    """Max RAG messages per guest session. 0 = unlimited guest use."""
    raw = os.environ.get("GUEST_MESSAGE_LIMIT", "2").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return max(0, n)


def _is_counted_rag_post(path: str, method: str) -> bool:
    if method != "POST":
        return False
    suffixes = ("/api/query", "/api/agent", "/api/agent/stream")
    return any(path.endswith(s) for s in suffixes)


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
    _migrate_google_sub()
    _migrate_user_chats()


def _migrate_user_chats() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_chats (
                user_id INTEGER PRIMARY KEY,
                messages_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


def _validate_chat_messages(messages: list) -> tuple[bool, str]:
    if len(messages) > 100:
        return False, "too many messages"
    for m in messages:
        if not isinstance(m, dict):
            return False, "invalid message"
        if m.get("role") not in ("user", "assistant"):
            return False, "invalid role"
        c = m.get("content")
        if not isinstance(c, str):
            return False, "invalid content"
        if len(c) > 500_000:
            return False, "message too long"
    return True, ""


def _migrate_google_sub() -> None:
    with _connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "google_sub" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
                ON users(google_sub) WHERE google_sub IS NOT NULL
                """
            )
            conn.commit()


def user_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0]) if row else 0


def create_user(email: str, password: str) -> bool:
    email = email.strip().lower()
    if not email or not password:
        return False
    ph = generate_password_hash(password)
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, ph),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def verify_login(email: str, password: str) -> int | None:
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if not row:
        return None
    if check_password_hash(row["password_hash"], password):
        return int(row["id"])
    return None


def get_user_email(user_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return row["email"] if row else None


def _user_row_by_email(email: str) -> sqlite3.Row | None:
    email = email.strip().lower()
    with _connect() as conn:
        return conn.execute(
            "SELECT id, password_hash, google_sub FROM users WHERE email = ?",
            (email,),
        ).fetchone()


def get_or_create_google_user(email: str, google_sub: str) -> int | None:
    """Link or create a user from Google OIDC. Returns user id or None."""
    email = email.strip().lower()
    if not email or not google_sub:
        return None
    ph = generate_password_hash(secrets.token_hex(32))
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE google_sub = ?",
            (google_sub,),
        ).fetchone()
        if row:
            return int(row["id"])
        row = conn.execute(
            "SELECT id, google_sub FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if row:
            if row["google_sub"] and row["google_sub"] != google_sub:
                logger.warning("Email %s already linked to another Google account", email)
                return None
            conn.execute(
                "UPDATE users SET google_sub = ? WHERE id = ?",
                (google_sub, int(row["id"])),
            )
            conn.commit()
            return int(row["id"])
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, google_sub) VALUES (?, ?, ?)",
                (email, ph, google_sub),
            )
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return None


def maybe_bootstrap_admin() -> None:
    email = (os.environ.get("ADMIN_EMAIL") or "").strip()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not email or not password:
        return
    init_db()
    if user_count() > 0:
        return
    if create_user(email, password):
        logger.info("Bootstrap: created admin user %s", email)


def _register_google_oauth(app) -> None:
    """Register Google OIDC routes when GOOGLE_CLIENT_ID/SECRET are set. Requires: pip install authlib"""
    cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    csec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if cid and csec and not _authlib_available():
        logger.warning(
            "GOOGLE_CLIENT_* is set but authlib is not installed. Run: pip install authlib"
        )
        return
    if not google_oauth_configured():
        return
    from authlib.integrations.flask_client import OAuth

    oauth = OAuth(app)
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"].strip(),
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"].strip(),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    @auth_bp.route("/google")
    def google_login():
        next_url = (request.args.get("next") or "/").strip() or "/"
        session["oauth_next"] = next_url
        redirect_uri = url_for("auth.google_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @auth_bp.route("/google/callback")
    def google_callback():
        try:
            token = oauth.google.authorize_access_token()
        except Exception as e:
            logger.warning("Google OAuth token exchange failed: %s", e)
            return redirect(url_for("auth.login", error="google_failed"))

        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                resp = oauth.google.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    token=token,
                )
                userinfo = resp.json()
            except Exception as e:
                logger.warning("Google userinfo fetch failed: %s", e)
                return redirect(url_for("auth.login", error="google_failed"))

        if not isinstance(userinfo, dict):
            return redirect(url_for("auth.login", error="google_failed"))

        email = (userinfo.get("email") or "").strip().lower()
        sub = (userinfo.get("sub") or "").strip()
        if not email or not sub:
            return redirect(url_for("auth.login", error="google_email"))

        uid = get_or_create_google_user(email, sub)
        if uid is None:
            return redirect(url_for("auth.login", error="google_link"))

        session["user_id"] = uid
        session["user_email"] = get_user_email(uid) or email
        session.pop("guest_msgs", None)
        session.permanent = True
        next_url = session.pop("oauth_next", None) or "/"
        return redirect(next_url)


def register_auth(app) -> None:
    """Register blueprint, DB init, before_request guard, and optional bootstrap."""
    init_db()
    maybe_bootstrap_admin()

    _register_google_oauth(app)
    app.register_blueprint(auth_bp)
    register_api_me_on_app(app)
    register_chat_api(app)

    if os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes"):
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    @app.before_request
    def _guest_or_auth():
        """No forced login on page load. Enforce guest RAG quota when AUTH_REQUIRED=1."""
        if not auth_required():
            return None
        path = request.path or ""
        if path.startswith("/auth") or path.startswith("/static"):
            return None
        if path.startswith("/main/auth") or path.startswith("/main/static"):
            return None
        if session.get("user_id"):
            return None
        lim = guest_message_limit()
        if lim <= 0:
            return None
        if not _is_counted_rag_post(path, request.method):
            return None
        used = int(session.get("guest_msgs") or 0)
        if used >= lim:
            return (
                jsonify(
                    {
                        "error": "guest_limit_exceeded",
                        "message": "Sign in to continue asking questions.",
                        "login_url": "/auth/login",
                        "guest_limit": lim,
                        "guest_messages_used": used,
                    }
                ),
                401,
            )
        return None

    @app.after_request
    def _increment_guest_after_rag(response):
        if not auth_required():
            return response
        if session.get("user_id"):
            return response
        lim = guest_message_limit()
        if lim <= 0:
            return response
        path = request.path or ""
        if not _is_counted_rag_post(path, request.method):
            return response
        if response.status_code < 200 or response.status_code >= 400:
            return response
        session["guest_msgs"] = int(session.get("guest_msgs") or 0) + 1
        session.modified = True
        return response

    @app.context_processor
    def _auth_ctx():
        return {
            "auth_required_flag": auth_required(),
            "current_user_email": session.get("user_email"),
            "guest_message_limit": guest_message_limit() if auth_required() else 0,
            "open_registration": open_registration(),
        }


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True) or {}
            email = (data.get("email") or "").strip()
            password = data.get("password") or ""
            next_url = data.get("next") or "/"
        else:
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            next_url = request.form.get("next") or request.args.get("next") or "/"
        uid = verify_login(email, password)
        if uid is None:
            row = _user_row_by_email(email)
            err = "Invalid email or password."
            if row and row["google_sub"]:
                err = "This account uses Google sign-in. Use the button below."
            if request.is_json:
                return jsonify({"error": err}), 401
            return (
                render_template(
                    "login.html",
                    error=err,
                    next_url=next_url,
                    open_registration=open_registration(),
                    google_oauth_enabled=google_oauth_configured(),
                ),
                401,
            )
        session["user_id"] = uid
        session["user_email"] = get_user_email(uid) or email
        session.pop("guest_msgs", None)
        session.permanent = True
        if request.is_json:
            return jsonify({"ok": True, "email": session["user_email"]})
        return redirect(next_url or "/")

    if request.method == "GET":
        next_url = request.args.get("next") or "/"
        err = None
        qe = request.args.get("error")
        if qe == "google_failed":
            err = "Google sign-in failed. Try again."
        elif qe == "google_email":
            err = "Google did not return an email for this account."
        elif qe == "google_link":
            err = "Could not link this Google account. The email may already be in use."
        return render_template(
            "login.html",
            next_url=next_url,
            error=err,
            open_registration=open_registration(),
            google_oauth_enabled=google_oauth_configured(),
        )


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    if request.is_json:
        return jsonify({"ok": True})
    return redirect("/")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if not open_registration():
        if request.is_json:
            return jsonify({"error": "Registration is disabled."}), 403
        return (
            render_template(
                "login.html",
                error="Registration is disabled.",
                next_url="/",
                open_registration=False,
                google_oauth_enabled=google_oauth_configured(),
            ),
            403,
        )
    if request.method == "GET":
        return render_template(
            "login.html",
            next_url=request.args.get("next") or "/",
            error=None,
            register_mode=True,
            open_registration=True,
            google_oauth_enabled=google_oauth_configured(),
        )

    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    password2 = request.form.get("password2") or ""
    next_url = request.form.get("next") or "/"
    if len(password) < 8:
        return (
            render_template(
                "login.html",
                error="Password must be at least 8 characters.",
                next_url=next_url,
                register_mode=True,
                open_registration=True,
                google_oauth_enabled=google_oauth_configured(),
            ),
            400,
        )
    if password != password2:
        return (
            render_template(
                "login.html",
                error="Passwords do not match.",
                next_url=next_url,
                register_mode=True,
                open_registration=True,
                google_oauth_enabled=google_oauth_configured(),
            ),
            400,
        )
    if not create_user(email, password):
        return (
            render_template(
                "login.html",
                error="That email is already registered.",
                next_url=next_url,
                register_mode=True,
                open_registration=True,
                google_oauth_enabled=google_oauth_configured(),
            ),
            400,
        )
    uid = verify_login(email, password)
    if uid is not None:
        session["user_id"] = uid
        session["user_email"] = get_user_email(uid) or email
        session.pop("guest_msgs", None)
        session.permanent = True
    return redirect(next_url or "/")


def register_chat_api(app) -> None:
    """GET/PUT /api/chat/state — persist one conversation thread per logged-in user."""

    @app.route("/api/chat/state", methods=["GET", "PUT"])
    def api_chat_state():
        uid = session.get("user_id")
        if not uid:
            return jsonify({"error": "login_required"}), 401
        if request.method == "GET":
            with _connect() as conn:
                row = conn.execute(
                    "SELECT messages_json FROM user_chats WHERE user_id = ?",
                    (uid,),
                ).fetchone()
            if not row:
                return jsonify({"messages": []})
            try:
                msgs = json.loads(row["messages_json"])
            except json.JSONDecodeError:
                msgs = []
            if not isinstance(msgs, list):
                msgs = []
            return jsonify({"messages": msgs})

        data = request.get_json(silent=True) or {}
        messages = data.get("messages")
        if not isinstance(messages, list):
            return jsonify({"error": "messages must be a list"}), 400
        ok, err = _validate_chat_messages(messages)
        if not ok:
            return jsonify({"error": err}), 400
        payload = json.dumps(messages)
        if len(payload) > 2_000_000:
            return jsonify({"error": "payload too large"}), 400
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO user_chats (user_id, messages_json, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                (uid, payload),
            )
            conn.commit()
        return jsonify({"ok": True})


def register_api_me_on_app(app) -> None:
    """Expose /api/auth/me at app root (for fetch from any mount path)."""

    @app.route("/api/auth/me")
    def api_auth_me():
        uid = session.get("user_id")
        if not auth_required():
            if not uid:
                return jsonify({"logged_in": False})
            return jsonify(
                {
                    "logged_in": True,
                    "email": session.get("user_email"),
                    "id": uid,
                }
            )
        lim = guest_message_limit()
        used = int(session.get("guest_msgs") or 0)
        if not uid:
            return jsonify(
                {
                    "logged_in": False,
                    "guest_limit": lim,
                    "guest_messages_used": used,
                    "guest_messages_remaining": (
                        max(0, lim - used) if lim > 0 else None
                    ),
                }
            )
        return jsonify(
            {
                "logged_in": True,
                "email": session.get("user_email"),
                "id": uid,
            }
        )

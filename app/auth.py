"""Email/password accounts for ImpactFund AI.

Every account has one of two roles:

* ``donor`` — can support campaigns.
* ``organizer`` — can create campaigns and use the AI planner.

The role is stored with the account and resolved from the email at login, so
the login form only asks for an email and password.
"""

import re
from functools import wraps
from urllib.parse import urlsplit

import psycopg
from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

ROLE_LABELS = {"donor": "Donor", "organizer": "Project creator"}
ROLES = set(ROLE_LABELS)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 200


def current_user():
    """Return the signed-in user from the session, or ``None``."""
    user_id = session.get("user_id")
    if user_id is None:
        return None

    role = session.get("user_role", "")
    return {
        "id": user_id,
        "email": session.get("user_email", ""),
        "name": session.get("user_name", ""),
        "role": role,
        "role_label": ROLE_LABELS.get(role, ""),
    }


def _start_session(user):
    """Store a freshly authenticated user, clearing any previous session."""
    session.clear()
    session["user_id"] = user[0]
    session["user_email"] = user[1]
    session["user_name"] = user[2]
    session["user_role"] = user[3]


def _safe_next(target):
    """Only allow redirects to paths inside this site."""
    if not target:
        return None
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None

    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def _login_target():
    """Where to send the user after login, preferring the page they came from."""
    if request.method == "GET":
        return request.full_path.rstrip("?")

    if request.referrer:
        referrer = urlsplit(request.referrer)
        if not referrer.netloc or referrer.netloc == request.host:
            target = referrer.path or "/"
            if referrer.query:
                target = f"{target}?{referrer.query}"
            return target
    return None


def _role_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("Please log in to continue.", "error")
                target = _login_target()
                return redirect(
                    url_for("login", next=target) if target else url_for("login")
                )
            if role and user["role"] != role:
                flash(
                    "Only project creator accounts can start a campaign.",
                    "error",
                )
                return redirect(url_for("home"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


login_required = _role_required()
organizer_required = _role_required("organizer")


def create_auth_bp(app, get_db):
    """Mount account routes on the app and expose the current user to templates."""

    @app.context_processor
    def inject_auth():
        return {
            "current_user": current_user(),
            "role_labels": ROLE_LABELS,
        }

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user():
            return redirect(url_for("home"))

        next_url = _safe_next(
            request.form.get("next") or request.args.get("next")
        )
        requested_role = request.args.get("role", "")
        default_role = requested_role if requested_role in ROLES else "donor"
        if not requested_role and next_url and "/campaigns/new" in next_url:
            default_role = "organizer"

        form = {
            "name": "",
            "email": "",
            "role": default_role,
        }
        error = None

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            role = request.form.get("role", "")

            form.update({"name": name, "email": email, "role": role})

            if not name:
                error = "Enter your name or organisation."
            elif len(name) > 120:
                error = "Keep your name under 120 characters."
            elif not EMAIL_RE.fullmatch(email):
                error = "Enter a valid email address."
            elif len(email) > 254:
                error = "That email address is too long."
            elif role not in ROLES:
                error = "Choose whether you are a donor or a project creator."
            elif len(password) < MIN_PASSWORD_LENGTH:
                error = f"Use at least {MIN_PASSWORD_LENGTH} characters for your password."
            elif len(password) > MAX_PASSWORD_LENGTH:
                error = "That password is too long."
            elif password != confirm:
                error = "Those passwords do not match."

            if error is None:
                try:
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO users
                                    (email, display_name, role, password_hash)
                                VALUES (%s, %s, %s, %s)
                                RETURNING id, email, display_name, role
                                """,
                                (
                                    email,
                                    name,
                                    role,
                                    generate_password_hash(password),
                                ),
                            )
                            user = cur.fetchone()
                except psycopg.errors.UniqueViolation:
                    error = "An account with that email already exists. Try logging in."
                else:
                    _start_session(user)
                    flash(
                        f"Welcome, {name}! Your {ROLE_LABELS[role].lower()} account is ready.",
                        "success",
                    )
                    return redirect(next_url or url_for("home"))

            if error:
                return (
                    render_template(
                        "signup.html",
                        form=form,
                        error=error,
                        next_url=next_url,
                    ),
                    400,
                )

        return render_template(
            "signup.html",
            form=form,
            error=None,
            next_url=next_url,
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user():
            return redirect(url_for("home"))

        next_url = _safe_next(
            request.form.get("next") or request.args.get("next")
        )
        email = ""
        error = None

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not email or not password:
                error = "Enter your email and password."
            else:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT id, email, display_name, role, password_hash
                            FROM users
                            WHERE email = %s
                            """,
                            (email,),
                        )
                        user = cur.fetchone()

                if user and check_password_hash(user[4], password):
                    _start_session(user)
                    flash(
                        f"Welcome back, {user[2]}! You're signed in as a "
                        f"{ROLE_LABELS[user[3]].lower()}.",
                        "success",
                    )
                    return redirect(next_url or url_for("home"))

                error = "Email or password is incorrect."

            if error:
                return (
                    render_template(
                        "login.html",
                        email=email,
                        error=error,
                        next_url=next_url,
                    ),
                    401,
                )

        return render_template(
            "login.html",
            email=email,
            error=None,
            next_url=next_url,
        )

    @app.post("/logout")
    def logout():
        session.clear()
        flash("You're logged out.", "success")
        return redirect(url_for("home"))

    return app

import os

import psycopg
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from app import ai, auth, paypal


def _secret_key():
    """Read the session signing key, refusing to guess on a hosted deployment."""
    key = os.getenv("FLASK_SECRET_KEY")
    if key:
        return key

    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set on Render; refusing to start with the "
            "development default, which would make session cookies forgeable."
        )

    return "dev-only-change-me"


def create_app():
    app = Flask(__name__)
    app.secret_key = _secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Render terminates TLS; enable this (SESSION_COOKIE_SECURE=1) so the
        # session cookie is never sent over plain HTTP.
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "").lower()
        in {"1", "true", "yes"},
    )

    # Honour the X-Forwarded-Proto header from the host's proxy so url_for()
    # builds https:// PayPal return URLs instead of http://.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    def get_db():
        return psycopg.connect(os.environ["DATABASE_URL"])

    @app.get("/")
    def home():
        q = request.args.get("q", "").strip()[:120]

        with get_db() as conn:
            with conn.cursor() as cur:
                if q:
                    like = f"%{q}%"
                    cur.execute("""
                        SELECT id, title, description, organiser,
                               goal, amount_raised, status, created_at
                        FROM campaigns
                        WHERE status = 'active'
                          AND (title ILIKE %s OR description ILIKE %s OR organiser ILIKE %s)
                        ORDER BY created_at DESC
                        LIMIT 50
                    """, (like, like, like))
                else:
                    cur.execute("""
                        SELECT id, title, description, organiser,
                               goal, amount_raised, status, created_at
                        FROM campaigns
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        LIMIT 50
                    """)
                campaigns = cur.fetchall()

        return render_template("index.html", campaigns=campaigns, q=q)

    @app.route("/campaigns/new", methods=["GET", "POST"])
    @auth.organizer_required
    def create_campaign():
        user = auth.current_user()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            organiser = request.form.get("organiser", "").strip() or user["name"]
            goal_raw = request.form.get("goal", "").strip()

            if not title or not description or not organiser or not goal_raw:
                flash("Please complete every field.", "error")
                return redirect(url_for("create_campaign"))

            try:
                goal = float(goal_raw)
                if not 0 < goal <= 9999999999.99:
                    raise ValueError
            except ValueError:
                flash("Enter a valid fundraising target.", "error")
                return redirect(url_for("create_campaign"))

            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO campaigns
                            (title, description, organiser, goal, status, owner_id)
                        VALUES (%s, %s, %s, %s, 'active', %s)
                        RETURNING id
                    """, (title, description, organiser, goal, user["id"]))
                    campaign_id = cur.fetchone()[0]

            flash("Campaign created successfully!", "success")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        return render_template("create_campaign.html")

    @app.get("/campaigns/<int:campaign_id>")
    def campaign_detail(campaign_id):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, description, organiser,
                           goal, amount_raised, status, created_at, owner_id
                    FROM campaigns
                    WHERE id = %s
                """, (campaign_id,))
                campaign = cur.fetchone()

        if campaign is None:
            return "Campaign not found", 404

        if request.args.get("paypal") == "cancel":
            flash("Donation cancelled — you have not been charged.", "error")

        return render_template("campaign_detail.html", campaign=campaign)

    @app.get("/health")
    def health():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    version = cur.fetchone()[0]

            return {
                "status": "healthy",
                "database": "connected",
                "postgresql": version.split(",")[0],
            }
        except Exception:
            app.logger.exception("Database health check failed")
            return {"status": "error", "database": "unavailable"}, 503

    auth.create_auth_bp(app, get_db)
    ai.create_ai_bp(app)
    paypal.create_paypal_bp(app, get_db)

    return app

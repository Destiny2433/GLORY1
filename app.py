from flask import (
    Flask, render_template, request, redirect, url_for, g,
    session, flash, jsonify, send_from_directory, abort, Response
)

import os
import json
import re
import secrets
import psycopg2

from psycopg2.extras import RealDictCursor
from datetime import datetime
from time import monotonic
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from functools import wraps
from dotenv import load_dotenv

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# ============================================================
# SUPABASE POSTGRESQL DATABASE
# ============================================================
#
# IMPORTANT:
#
# DATABASE_URL must be the PostgreSQL connection string from
# Supabase.
#
# Example:
#
# DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-xx.pooler.supabase.com:6543/postgres
#
# Do NOT put SUPABASE_KEY here.
#
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured. "
        "Add your Supabase PostgreSQL connection string "
        "to your .env file or Render Environment Variables."
    )

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "gallery")

supabase_client = None
if create_client and SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app.config["UPLOAD_FOLDER"] = os.path.join(
    BASE_DIR,
    "static",
    "images"
)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or secrets.token_hex(32)
)

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
)

app.config["MAX_FORM_MEMORY_SIZE"] = 512 * 1024

app.config["SEND_FILE_MAX_AGE_DEFAULT"] = (
    0
    if os.environ.get("FLASK_DEBUG") == "1"
    else 31536000
)

app.config["TEMPLATES_AUTO_RELOAD"] = (
    os.environ.get("FLASK_DEBUG") == "1"
)


# ============================================================
# ADMIN
# ============================================================

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH"
)


# ============================================================
# UPLOADS / SECURITY
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp"
}

RATE_LIMIT_WINDOW = 60

RATE_LIMIT_MAX_REQUESTS = 10

rate_limit_store = {}


os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

os.makedirs(
    os.path.join(
        app.config["UPLOAD_FOLDER"],
        "Gallery"
    ),
    exist_ok=True
)


# ============================================================
# DATABASE WRAPPER
# ============================================================

class Database:
    """
    PostgreSQL compatibility wrapper.

    The rest of the application uses ? placeholders.
    PostgreSQL uses %s.

    This wrapper automatically converts:
        ?
    into:
        %s
    """

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):

        if not query:
            raise ValueError("Database query cannot be empty.")

        query = query.replace("?", "%s")

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params or ()
        )

        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    database = getattr(
        g,
        "_database",
        None
    )

    if database is None:

        connection = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )

        database = g._database = Database(
            connection
        )

    return database


# ============================================================
# DATABASE SCHEMA
# ============================================================

def ensure_column(
    db,
    table,
    column,
    definition
):

    # Table/column names cannot be parameterized.
    # These names are internal constants, not user input.

    result = db.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = ?
        AND column_name = ?
        """,
        (
            table,
            column
        )
    ).fetchone()

    if not result:

        db.execute(
            f"""
            ALTER TABLE "{table}"
            ADD COLUMN "{column}" {definition}
            """
        )


def initialize_database():

    db = get_db()

    try:

        # ====================================================
        # CONTACT MESSAGES
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id SERIAL PRIMARY KEY,
                name TEXT,
                email TEXT,
                subject TEXT,
                message TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ====================================================
        # VOLUNTEERS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS volunteer_applications (
                id SERIAL PRIMARY KEY,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                age TEXT,
                team TEXT,
                skills TEXT,
                availability TEXT,
                experience TEXT,
                message TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ====================================================
        # NEWSLETTER
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS newsletter_subscribers (
                id SERIAL PRIMARY KEY,
                email TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ====================================================
        # EVENTS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title TEXT,
                event_date TEXT,
                flyer_image TEXT,
                slug TEXT,
                edition_year INTEGER,
                parent_event_id INTEGER,
                event_type TEXT DEFAULT 'concert',
                month TEXT,
                day_label TEXT,
                start_time TEXT,
                end_time TEXT,
                venue TEXT,
                description TEXT,
                is_published INTEGER DEFAULT 1,
                registration_enabled INTEGER DEFAULT 0,
                published_at TIMESTAMP
            )
        """)


        # ====================================================
        # GALLERY
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS gallery (
                id SERIAL PRIMARY KEY,
                image_path TEXT
            )
        """)


        # ====================================================
        # MINISTERS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS ministers (
                id SERIAL PRIMARY KEY,
                name TEXT,
                role TEXT,
                image TEXT,
                bio TEXT
            )
        """)


        # ====================================================
        # HERO
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS hero (
                id SERIAL PRIMARY KEY,
                main_title TEXT,
                subtitle TEXT,
                media_path TEXT,
                livestream_url TEXT
            )
        """)


        # ====================================================
        # PUSH SUBSCRIPTIONS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                audience TEXT NOT NULL DEFAULT 'visitor',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ====================================================
        # SITE SETTINGS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


        # ====================================================
        # EXISTING DATABASE SAFETY
        # ====================================================

        ensure_column(
            db,
            "events",
            "slug",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "edition_year",
            "INTEGER"
        )

        ensure_column(
            db,
            "events",
            "parent_event_id",
            "INTEGER"
        )

        ensure_column(
            db,
            "events",
            "event_type",
            "TEXT DEFAULT 'concert'"
        )

        ensure_column(
            db,
            "events",
            "month",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "day_label",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "start_time",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "end_time",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "venue",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "description",
            "TEXT"
        )

        ensure_column(
            db,
            "events",
            "is_published",
            "INTEGER DEFAULT 1"
        )

        ensure_column(
            db,
            "events",
            "registration_enabled",
            "INTEGER DEFAULT 0"
        )

        ensure_column(
            db,
            "events",
            "published_at",
            "TIMESTAMP"
        )

        ensure_column(
            db,
            "volunteer_applications",
            "skills",
            "TEXT"
        )

        ensure_column(
            db,
            "volunteer_applications",
            "availability",
            "TEXT"
        )

        ensure_column(
            db,
            "volunteer_applications",
            "experience",
            "TEXT"
        )

        ensure_column(
            db,
            "volunteer_applications",
            "message",
            "TEXT"
        )

        ensure_column(
            db,
            "ministers",
            "bio",
            "TEXT"
        )

        ensure_column(
            db,
            "hero",
            "livestream_url",
            "TEXT"
        )


        # ====================================================
        # CREATE / REPAIR EVENT SLUGS
        # ====================================================

        db.execute("""
            UPDATE events
            SET slug = LOWER(
                REGEXP_REPLACE(
                    TRIM(title),
                    '[^a-zA-Z0-9]+',
                    '-',
                    'g'
                )
            )
            WHERE slug IS NULL
            OR slug = ''
        """)


        # ====================================================
        # DEFAULT HERO
        # ====================================================

        hero_exists = db.execute(
            """
            SELECT id
            FROM hero
            LIMIT 1
            """
        ).fetchone()

        if not hero_exists:

            db.execute(
                """
                INSERT INTO hero (
                    main_title,
                    subtitle,
                    media_path,
                    livestream_url
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "WELCOME TO ECWA GLORY",
                    "Raise your heart and voice in praise.",
                    "",
                    "https://www.youtube.com/watch?v=LMLp-aBI0BE"
                )
            )


        db.commit()

    except Exception:

        db.rollback()

        raise


# ============================================================
# INITIALIZE DATABASE
# ============================================================

with app.app_context():

    initialize_database()


# ============================================================
# LOGIN
# ============================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not session.get("admin_logged_in"):

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# CSRF
# ============================================================

def csrf_token():

    token = session.get(
        "_csrf_token"
    )

    if not token:

        token = secrets.token_urlsafe(32)

        session["_csrf_token"] = token

    return token


app.jinja_env.globals["csrf_token"] = csrf_token


# ============================================================
# REQUEST PROTECTION
# ============================================================

@app.before_request
def protect_requests():

    if request.method != "POST":
        return None


    # ========================================================
    # RATE LIMIT
    # ========================================================

    now = monotonic()

    address = request.remote_addr or "unknown"

    recent = [
        stamp
        for stamp in rate_limit_store.get(
            address,
            []
        )
        if now - stamp < RATE_LIMIT_WINDOW
    ]

    if len(recent) >= RATE_LIMIT_MAX_REQUESTS:

        return jsonify(
            success=False,
            message="Too many requests. Please try again shortly."
        ), 429

    recent.append(now)

    rate_limit_store[address] = recent


    # ========================================================
    # CSRF
    # ========================================================

    session_token = session.get(
        "_csrf_token"
    )

    if request.is_json:

        supplied = request.headers.get(
            "X-CSRF-Token"
        )

    else:

        supplied = (
            request.form.get("_csrf_token")
            or request.headers.get("X-CSRF-Token")
        )

    if (
        not session_token
        or not supplied
        or not secrets.compare_digest(
            str(supplied),
            str(session_token)
        )
    ):

        return jsonify(
            success=False,
            message="Invalid security token."
        ), 400

    return None


# ============================================================
# LIVESTREAM
# ============================================================

def normalize_livestream_url(value):

    raw = (value or "").strip()

    if not raw:

        return (
            "https://www.youtube.com/embed/"
            "LMLp-aBI0BE"
        )

    if (
        raw.startswith(
            "https://www.youtube.com/embed/"
        )
        or raw.startswith(
            "http://www.youtube.com/embed/"
        )
        or raw.startswith(
            "https://youtube.com/embed/"
        )
        or raw.startswith(
            "https://www.youtube.com/live/"
        )
        or raw.startswith(
            "https://youtube.com/live/"
        )
    ):

        return raw

    if "youtube.com/watch?v=" in raw:

        video_id = re.search(
            r"[?&]v=([A-Za-z0-9_-]+)",
            raw
        )

        if video_id:

            return (
                "https://www.youtube.com/embed/"
                f"{video_id.group(1)}"
            )

    if "youtu.be/" in raw:

        video_id = re.search(
            r"youtu\.be/([A-Za-z0-9_-]+)",
            raw
        )

        if video_id:

            return (
                "https://www.youtube.com/embed/"
                f"{video_id.group(1)}"
            )

    return raw


def get_livestream_link(value):

    raw = (value or "").strip()

    if not raw:

        return (
            "https://www.youtube.com/live/"
            "LMLp-aBI0BE"
        )

    return raw


# ============================================================
# IMAGE UPLOADS
# ============================================================

def allowed_image(filename):

    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_IMAGE_EXTENSIONS
    )


def save_image(
    upload,
    subdirectory=""
):

    if not upload or not upload.filename:
        return None

    if not allowed_image(upload.filename):
        raise ValueError("Only JPG, JPEG, PNG, GIF, and WebP images are allowed.")

    filename = secure_filename(upload.filename)
    if not filename:
        raise ValueError("The uploaded image has an invalid filename.")

    name, extension = os.path.splitext(filename)
    
    # Generate SEO-friendly slug for the filename
    safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not safe_name:
        safe_name = "image"
        
    unique_suffix = secrets.token_hex(4)
    final_filename = f"{safe_name}-{unique_suffix}{extension.lower()}"
    
    relative_path = f"{subdirectory}/{final_filename}".strip("/")

    # If Supabase Storage is configured, use it
    if supabase_client:
        try:
            file_bytes = upload.read()
            supabase_client.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                file=file_bytes,
                path=relative_path,
                file_options={"content-type": upload.content_type}
            )
            # Return the public URL
            public_url = supabase_client.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(relative_path)
            return public_url
        except Exception as e:
            print(f"Supabase upload error: {e}")
            # Fallback to local storage if supabase fails
            upload.seek(0)

    # Local Storage fallback
    target_dir = os.path.join(
        app.config["UPLOAD_FOLDER"],
        subdirectory
    )

    os.makedirs(
        target_dir,
        exist_ok=True
    )

    upload.save(
        os.path.join(
            target_dir,
            final_filename
        )
    )

    return os.path.join(
        subdirectory,
        final_filename
    ).replace(
        "\\",
        "/"
    )


# ============================================================
# FORM HELPERS
# ============================================================

def required_form_values(fields):

    values = {
        field: request.form.get(
            field,
            ""
        ).strip()
        for field in fields
    }

    missing = [
        field
        for field, value in values.items()
        if not value
    ]

    if missing:

        raise ValueError(
            "Please complete all required fields."
        )

    return values


# ============================================================
# EVENTS
# ============================================================

def event_slug(
    title,
    event_id=None
):

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        (title or "").lower()
    ).strip("-") or "event"

    if event_id:

        return f"{value}-{event_id}"

    return value


def event_status_label(event_date):

    if not event_date:

        return "Upcoming"

    date_text = str(
        event_date
    ).strip()

    for fmt in (
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%b %d %Y",
        "%B %d %Y",
        "%d/%m/%Y",
        "%m/%d/%Y"
    ):

        try:

            parsed = datetime.strptime(
                date_text,
                fmt
            ).date()

            if parsed < datetime.utcnow().date():

                return "Completed"

            return "Upcoming"

        except ValueError:

            continue

    return "Upcoming"


# ============================================================
# PUSH NOTIFICATIONS
# ============================================================

def send_push_notification(
    title,
    body,
    url,
    audience="visitor"
):

    private_key = os.environ.get(
        "VAPID_PRIVATE_KEY"
    )

    subject = os.environ.get(
        "VAPID_SUBJECT"
    )

    if (
        not webpush
        or not private_key
        or not subject
    ):

        return 0

    db = get_db()

    subscriptions = db.execute(
        """
        SELECT *
        FROM push_subscriptions
        WHERE audience=?
        AND active=1
        """,
        (audience,)
    ).fetchall()

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    sent = 0

    for subscription in subscriptions:

        try:

            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {
                        "p256dh": subscription["p256dh"],
                        "auth": subscription["auth"]
                    }
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={
                    "sub": subject
                }
            )

            sent += 1

        except WebPushException as error:

            response = getattr(
                error,
                "response",
                None
            )

            if (
                response is not None
                and response.status_code in {
                    404,
                    410
                }
            ):

                db.execute(
                    """
                    UPDATE push_subscriptions
                    SET
                        active=0,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        subscription["id"],
                    )
                )

    db.commit()

    return sent


# ============================================================
# CLOSE DATABASE
# ============================================================

@app.teardown_appcontext
def close_connection(exception):

    db = getattr(
        g,
        "_database",
        None
    )

    if db is not None:
        if exception:
            db.rollback()
        db.close()


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(success=False, message="Not found"), 404
    return render_template("404.html"), 404

@app.errorhandler(403)
def forbidden(e):
    if request.path.startswith("/api/"):
        return jsonify(success=False, message="Forbidden"), 403
    return render_template("404.html"), 403

@app.errorhandler(500)
def internal_server_error(e):
    # Log the error internally (Flask does this automatically)
    if getattr(g, "_database", None):
        g._database.rollback()
    
    if request.path.startswith("/api/"):
        return jsonify(success=False, message="Internal server error"), 500
    
    # Render a user-friendly 500 page
    return render_template("500.html"), 500


# ============================================================
# SECURITY HEADERS
# ============================================================

@app.after_request
def add_security_headers(response):

    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff"
    )

    response.headers.setdefault(
        "X-Frame-Options",
        "SAMEORIGIN"
    )

    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin"
    )

    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()"
    )

    return response


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    db = get_db()

    hero = db.execute(
        """
        SELECT *
        FROM hero
        LIMIT 1
        """
    ).fetchone()

    ministers = db.execute(
        """
        SELECT *
        FROM ministers
        ORDER BY id ASC
        """
    ).fetchall()

    upcoming_event = db.execute(
        """
        SELECT *
        FROM events
        WHERE COALESCE(is_published, 1)=1
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    livestream_url = ""

    if hero:

        livestream_url = (
            hero.get("livestream_url")
            or ""
        )

    return render_template(
        "index.html",
        hero=hero,
        ministers=ministers,
        upcoming_event=upcoming_event,
        livestream_embed_url=normalize_livestream_url(
            livestream_url
        ),
        livestream_link_url=get_livestream_link(
            livestream_url
        )
    )


# ============================================================
# STATIC PWA FILES
# ============================================================

@app.route("/sw.js")
def serve_sw():

    return send_from_directory(
        os.path.join(
            BASE_DIR,
            "static"
        ),
        "sw.js",
        mimetype="application/javascript"
    )


@app.route("/manifest.json")
def serve_manifest():

    return send_from_directory(
        os.path.join(
            BASE_DIR,
            "static"
        ),
        "manifest.json",
        mimetype="application/manifest+json"
    )


# ============================================================
# CHECK MESSAGES
# ============================================================

@app.route("/api/check_messages")
@login_required
def check_messages():

    last_id = request.args.get(
        "last_id",
        0,
        type=int
    )

    db = get_db()

    new_msgs = db.execute(
        """
        SELECT
            id,
            name,
            subject
        FROM contact_messages
        WHERE id > ?
        ORDER BY id ASC
        """,
        (last_id,)
    ).fetchall()

    return jsonify(
        [
            dict(message)
            for message in new_msgs
        ]
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
def about():

    return render_template(
        "About.html"
    )


# ============================================================
# GALLERY
# ============================================================

@app.route("/gallery_page")
def gallery_page():

    db = get_db()

    images = db.execute(
        """
        SELECT *
        FROM gallery
        ORDER BY id DESC
        """
    ).fetchall()

    return render_template(
        "gallery.html",
        images=images
    )


@app.route("/gallery")
def gallery():

    return redirect(
        url_for("gallery_page")
    )


# ============================================================
# EVENTS
# ============================================================

@app.route("/events")
def events():

    event_rows = get_db().execute(
        """
        SELECT *
        FROM events
        WHERE COALESCE(is_published, 1)=1
        ORDER BY event_date ASC, id ASC
        """
    ).fetchall()

    safe_rows = []

    for event in event_rows:

        event_payload = dict(event)

        event_payload["status_label"] = (
            event_status_label(
                event.get("event_date")
            )
        )

        safe_rows.append(
            event_payload
        )

    return render_template(
        "events.html",
        events=safe_rows
    )


@app.route("/events/<slug>")
def event_detail(slug):

    event = get_db().execute(
        """
        SELECT *
        FROM events
        WHERE slug=?
        AND COALESCE(is_published, 1)=1
        LIMIT 1
        """,
        (slug,)
    ).fetchone()

    if event is None:

        abort(404)

    return render_template(
        "event_detail.html",
        event=event
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
def notifications():

    return render_template(
        "notifications.html",
        vapid_public_key=os.environ.get(
            "VAPID_PUBLIC_KEY",
            ""
        )
    )


# ============================================================
# PUSH SUBSCRIBE
# ============================================================

@app.post("/api/push/subscribe")
def subscribe_push():

    payload = request.get_json(
        silent=True
    ) or {}

    keys = payload.get(
        "keys"
    ) or {}

    endpoint = str(
        payload.get(
            "endpoint",
            ""
        )
    ).strip()

    p256dh = str(
        keys.get(
            "p256dh",
            ""
        )
    ).strip()

    auth = str(
        keys.get(
            "auth",
            ""
        )
    ).strip()

    audience = str(
        payload.get(
            "audience",
            "visitor"
        )
    ).strip() or "visitor"

    if (
        not endpoint
        or not p256dh
        or not auth
        or audience not in {
            "visitor",
            "admin"
        }
    ):

        return jsonify(
            success=False,
            message="Invalid push subscription."
        ), 400

    if (
        audience == "admin"
        and not session.get(
            "admin_logged_in"
        )
    ):

        return jsonify(
            success=False,
            message="Admin authentication required."
        ), 403

    db = get_db()

    db.execute(
        """
        INSERT INTO push_subscriptions (
            endpoint,
            p256dh,
            auth,
            audience,
            active,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, 1, CURRENT_TIMESTAMP
        )

        ON CONFLICT(endpoint)

        DO UPDATE SET
            p256dh=EXCLUDED.p256dh,
            auth=EXCLUDED.auth,
            audience=EXCLUDED.audience,
            active=1,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            endpoint,
            p256dh,
            auth,
            audience
        )
    )

    db.commit()

    return jsonify(
        success=True
    )


# ============================================================
# PUSH UNSUBSCRIBE
# ============================================================

@app.post("/api/push/unsubscribe")
def unsubscribe_push():

    payload = request.get_json(
        silent=True
    ) or {}

    endpoint = str(
        payload.get(
            "endpoint",
            ""
        )
    ).strip()

    if not endpoint:

        return jsonify(
            success=False,
            message="Subscription endpoint is required."
        ), 400

    db = get_db()

    db.execute(
        """
        UPDATE push_subscriptions
        SET
            active=0,
            updated_at=CURRENT_TIMESTAMP
        WHERE endpoint=?
        """,
        (endpoint,)
    )

    db.commit()

    return jsonify(
        success=True
    )


# ============================================================
# ADMIN EVENTS
# ============================================================

@app.route(
    "/admin/events",
    methods=["GET", "POST"]
)
@login_required
def admin_events():

    db = get_db()

    if request.method == "POST":

        action = request.form.get(
            "action",
            "create"
        )

        event_id = request.form.get(
            "event_id",
            type=int
        )

        try:

            # ------------------------------------------------
            # DELETE
            # ------------------------------------------------

            if action == "delete" and event_id:

                db.execute(
                    """
                    DELETE FROM events
                    WHERE id=?
                    """,
                    (event_id,)
                )


            # ------------------------------------------------
            # CREATE / UPDATE
            # ------------------------------------------------

            elif action in {
                "create",
                "update"
            }:

                values = required_form_values([
                    "title",
                    "event_date",
                    "event_type"
                ])

                existing = None

                if event_id:

                    existing = db.execute(
                        """
                        SELECT is_published
                        FROM events
                        WHERE id=?
                        """,
                        (event_id,)
                    ).fetchone()

                published = (
                    1
                    if request.form.get(
                        "is_published"
                    ) == "on"
                    else 0
                )

                fields = (
                    values["title"],
                    event_slug(
                        values["title"],
                        event_id
                    ),
                    request.form.get(
                        "edition_year",
                        type=int
                    ),
                    request.form.get(
                        "parent_event_id",
                        type=int
                    ),
                    values["event_type"],
                    request.form.get(
                        "month",
                        ""
                    ).strip(),
                    request.form.get(
                        "day_label",
                        ""
                    ).strip(),
                    values["event_date"],
                    request.form.get(
                        "start_time",
                        ""
                    ).strip(),
                    request.form.get(
                        "end_time",
                        ""
                    ).strip(),
                    request.form.get(
                        "venue",
                        ""
                    ).strip(),
                    request.form.get(
                        "description",
                        ""
                    ).strip(),
                    published,
                    (
                        1
                        if request.form.get(
                            "registration_enabled"
                        ) == "on"
                        else 0
                    )
                )

                if action == "create":

                    cursor = db.execute(
                        """
                        INSERT INTO events (
                            title,
                            slug,
                            edition_year,
                            parent_event_id,
                            event_type,
                            month,
                            day_label,
                            event_date,
                            start_time,
                            end_time,
                            venue,
                            description,
                            is_published,
                            registration_enabled
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?
                        )
                        RETURNING id
                        """,
                        fields
                    )

                    result = cursor.fetchone()

                    event_id = result["id"]

                    # Repair slug now that we have ID.
                    db.execute(
                        """
                        UPDATE events
                        SET slug=?
                        WHERE id=?
                        """,
                        (
                            event_slug(
                                values["title"],
                                event_id
                            ),
                            event_id
                        )
                    )

                else:

                    db.execute(
                        """
                        UPDATE events
                        SET
                            title=?,
                            slug=?,
                            edition_year=?,
                            parent_event_id=?,
                            event_type=?,
                            month=?,
                            day_label=?,
                            event_date=?,
                            start_time=?,
                            end_time=?,
                            venue=?,
                            description=?,
                            is_published=?,
                            registration_enabled=?
                        WHERE id=?
                        """,
                        fields + (
                            event_id,
                        )
                    )


                # ------------------------------------------------
                # PUBLISH EVENT
                # ------------------------------------------------

                if published and (
                    existing is None
                    or not existing["is_published"]
                ):

                    db.execute(
                        """
                        UPDATE events
                        SET published_at =
                            COALESCE(
                                published_at,
                                CURRENT_TIMESTAMP
                            )
                        WHERE id=?
                        """,
                        (event_id,)
                    )

                    send_push_notification(
                        values["title"],
                        request.form.get(
                            "description",
                            ""
                        ).strip()[:160],
                        url_for(
                            "event_detail",
                            slug=event_slug(
                                values["title"],
                                event_id
                            ),
                            _external=True
                        )
                    )


            db.commit()

            flash(
                "Event changes saved."
            )

        except ValueError as error:

            db.rollback()

            flash(
                str(error)
            )

        except Exception as error:

            db.rollback()

            flash(
                f"Error: {str(error)}"
            )

        return redirect(
            url_for(
                "admin_events"
            )
        )


    event_rows = db.execute(
        """
        SELECT *
        FROM events
        ORDER BY
            edition_year DESC NULLS LAST,
            event_date ASC,
            id ASC
        """
    ).fetchall()

    return render_template(
        "admin_events.html",
        events=event_rows
    )


# ============================================================
# ADMIN GALLERY
# ============================================================

@app.route(
    "/admin/gallery",
    methods=["GET", "POST"]
)
@login_required
def admin_gallery():

    db = get_db()

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        try:

            if action == "upload":

                for upload in request.files.getlist(
                    "images"
                ):

                    if upload and upload.filename:

                        image_path = save_image(
                            upload,
                            "Gallery"
                        )

                        db.execute(
                            """
                            INSERT INTO gallery (
                                image_path
                            )
                            VALUES (?)
                            """,
                            (image_path,)
                        )


            elif action == "delete":

                image_id = request.form.get(
                    "image_id",
                    type=int
                )

                if image_id:

                    db.execute(
                        """
                        DELETE FROM gallery
                        WHERE id=?
                        """,
                        (image_id,)
                    )


            db.commit()

        except Exception as error:

            db.rollback()

            flash(
                f"Gallery error: {str(error)}"
            )

        return redirect(
            url_for(
                "admin_gallery"
            )
        )


    images = db.execute(
        """
        SELECT *
        FROM gallery
        ORDER BY id DESC
        """
    ).fetchall()

    return render_template(
        "admin_gallery.html",
        images=images
    )


# ============================================================
# VOLUNTEER DETAIL
# ============================================================

@app.route(
    "/admin/volunteers/<int:volunteer_id>"
)
@login_required
def volunteer_detail(
    volunteer_id
):

    volunteer_application = get_db().execute(
        """
        SELECT *
        FROM volunteer_applications
        WHERE id=?
        """,
        (volunteer_id,)
    ).fetchone()

    if volunteer_application is None:

        abort(404)

    return render_template(
        "volunteer_detail.html",
        volunteer=volunteer_application
    )


# ============================================================
# SUPPORT
# ============================================================

@app.route("/support")
def support():

    return render_template(
        "support.html"
    )


# ============================================================
# VOLUNTEER
# ============================================================

@app.route(
    "/volunteer",
    methods=["GET", "POST"]
)
def volunteer():

    if request.method == "POST":

        try:

            values = required_form_values([
                "full_name",
                "email",
                "phone",
                "team"
            ])

            if (
                "@" not in values["email"]
            ):

                raise ValueError(
                    "Please enter a valid email address."
                )

            db = get_db()

            db.execute(
                """
                INSERT INTO volunteer_applications (
                    full_name,
                    email,
                    phone,
                    age,
                    team,
                    skills,
                    availability,
                    experience,
                    message
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    values["full_name"],
                    values["email"],
                    values["phone"],
                    request.form.get(
                        "age",
                        ""
                    ).strip(),
                    values["team"],
                    request.form.get(
                        "skills",
                        ""
                    ).strip(),
                    request.form.get(
                        "availability",
                        ""
                    ).strip(),
                    request.form.get(
                        "experience",
                        ""
                    ).strip(),
                    request.form.get(
                        "message",
                        ""
                    ).strip()
                )
            )

            db.commit()

            send_push_notification(
                "New volunteer application",
                (
                    f"{values['full_name']} "
                    f"applied for the "
                    f"{values['team']} team."
                ),
                url_for(
                    "admin",
                    _external=True
                ),
                audience="admin"
            )

            return redirect(
                url_for(
                    "thank_you",
                    type="volunteer"
                )
            )

        except ValueError as error:

            flash(
                str(error)
            )

        except Exception as error:

            flash(
                f"Unable to submit application: {str(error)}"
            )

    return render_template(
        "volunteer.html"
    )


# ============================================================
# CONTACT
# ============================================================

@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        try:

            values = required_form_values([
                "name",
                "email",
                "message"
            ])

            if (
                "@" not in values["email"]
            ):

                raise ValueError(
                    "Please enter a valid email address."
                )

            db = get_db()

            db.execute(
                """
                INSERT INTO contact_messages (
                    name,
                    email,
                    subject,
                    message
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    values["name"],
                    values["email"],
                    request.form.get(
                        "subject",
                        ""
                    ).strip(),
                    values["message"]
                )
            )

            db.commit()

            send_push_notification(
                "New visitor message",
                (
                    f"{values['name']} "
                    f"sent a new message."
                ),
                url_for(
                    "admin",
                    _external=True
                ),
                audience="admin"
            )

            return redirect(
                url_for(
                    "thank_you",
                    type="contact"
                )
            )

        except ValueError as error:

            return render_template(
                "contact.html",
                error=str(error)
            ), 400

        except Exception as error:

            return render_template(
                "contact.html",
                error="Unable to send your message. Please try again."
            ), 500

    return render_template(
        "contact.html"
    )


# ============================================================
# NEWSLETTER
# ============================================================

@app.route(
    "/newsletter",
    methods=["POST"]
)
def newsletter():

    email = request.form.get(
        "email",
        ""
    ).strip()

    if email:

        if "@" not in email:

            flash(
                "Please enter a valid email address."
            )

            return redirect(
                url_for(
                    "index"
                )
            )

        db = get_db()

        db.execute(
            """
            INSERT INTO newsletter_subscribers (
                email
            )
            VALUES (?)
            """,
            (email,)
        )

        db.commit()

    return redirect(
        url_for(
            "thank_you",
            type="newsletter"
        )
    )


# ============================================================
# THANK YOU
# ============================================================

@app.route("/thank-you")
def thank_you():

    t = request.args.get(
        "type"
    )

    msg = "Submission Successful!"

    if t == "volunteer":

        msg = "Thank you for volunteering!"

    elif t == "newsletter":

        msg = "Thank you for subscribing!"

    elif t == "contact":

        msg = "Thank you for contacting us!"

    return render_template(
        "thank-you.html",
        message=msg
    )


# ============================================================
# MINISTER PAGES
# ============================================================

@app.route("/frank.html")
def frank():

    return render_template(
        "frank.html"
    )


@app.route("/kaywonder.html")
def kaywonder():

    return render_template(
        "kaywonder.html"
    )


@app.route("/akinyemi.html")
def akinyemi():

    return render_template(
        "akinyemi.html"
    )


@app.route("/babatunde.html")
def babatunde():

    return render_template(
        "babatunde.html"
    )


@app.route("/pelumi.html")
def pelumi():

    return render_template(
        "pelumi.html"
    )


@app.route(
    "/minister/<int:minister_id>"
)
def minister_profile(
    minister_id
):

    minister = get_db().execute(
        """
        SELECT *
        FROM ministers
        WHERE id=?
        """,
        (minister_id,)
    ).fetchone()

    if minister is None:

        abort(404)

    return render_template(
        "minister-profile.html",
        minister=minister
    )


# ============================================================
# 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        password_valid = False


        # ====================================================
        # HASHED PASSWORD
        # ====================================================

        if (
            ADMIN_PASSWORD_HASH
            and password
        ):

            try:

                password_valid = check_password_hash(
                    ADMIN_PASSWORD_HASH,
                    password
                )

            except Exception:

                password_valid = False


        # ====================================================
        # PLAIN PASSWORD FALLBACK
        # ====================================================

        if (
            not password_valid
            and ADMIN_PASSWORD
        ):

            try:

                password_valid = secrets.compare_digest(
                    password,
                    ADMIN_PASSWORD
                )

            except Exception:

                password_valid = False


        if password_valid:

            session.clear()

            session["admin_logged_in"] = True

            # Generate fresh CSRF token after login.
            session["_csrf_token"] = secrets.token_urlsafe(
                32
            )

            return redirect(
                url_for("admin")
            )


        flash(
            "Invalid Admin Password"
        )


    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
@login_required
def admin():

    db = get_db()

    if request.method == "POST":

        action = request.form.get(
            "admin_action"
        )

        try:

            # =================================================
            # HERO
            # =================================================

            if action == "update_hero":

                livestream_url = request.form.get(
                    "livestream_url",
                    ""
                ).strip()

                db.execute(
                    """
                    UPDATE hero
                    SET
                        main_title=?,
                        subtitle=?,
                        livestream_url=?
                    WHERE id=(
                        SELECT id
                        FROM hero
                        ORDER BY id
                        LIMIT 1
                    )
                    """,
                    (
                        request.form.get(
                            "main_title",
                            ""
                        ).strip(),

                        request.form.get(
                            "subtitle",
                            ""
                        ).strip(),

                        livestream_url
                    )
                )


            # =================================================
            # EVENT
            # =================================================

            elif action == "update_event":

                title = request.form.get(
                    "title",
                    ""
                ).strip()

                date = request.form.get(
                    "event_date",
                    ""
                ).strip()

                if not title or not date:

                    raise ValueError(
                        "Event title and date are required."
                    )

                file = request.files.get(
                    "flyer_image"
                )

                event = db.execute(
                    """
                    SELECT *
                    FROM events
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()

                img = (
                    event["flyer_image"]
                    if event
                    and event.get("flyer_image")
                    else "default.jpg"
                )

                if file and file.filename:

                    img = save_image(
                        file
                    )

                if event:

                    db.execute(
                        """
                        UPDATE events
                        SET
                            title=?,
                            event_date=?,
                            flyer_image=?
                        WHERE id=?
                        """,
                        (
                            title,
                            date,
                            img,
                            event["id"]
                        )
                    )

                else:

                    db.execute(
                        """
                        INSERT INTO events (
                            title,
                            event_date,
                            flyer_image,
                            slug,
                            is_published
                        )
                        VALUES (?, ?, ?, ?, 1)
                        """,
                        (
                            title,
                            date,
                            img,
                            event_slug(title)
                        )
                    )


            # =================================================
            # ADD MINISTER
            # =================================================

            elif action == "add_minister":

                n = request.form.get(
                    "name",
                    ""
                ).strip()

                r = request.form.get(
                    "role",
                    ""
                ).strip()

                bio = request.form.get(
                    "bio",
                    ""
                ).strip()

                if not n:

                    raise ValueError(
                        "Minister name is required."
                    )

                f = request.files.get(
                    "image"
                )

                img = (
                    save_image(f)
                    if f and f.filename
                    else "default.jpg"
                )

                db.execute(
                    """
                    INSERT INTO ministers (
                        name,
                        role,
                        image,
                        bio
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        n,
                        r,
                        img,
                        bio
                    )
                )


            # =================================================
            # EDIT MINISTER
            # =================================================

            elif action == "edit_minister":

                mid = request.form.get(
                    "minister_id",
                    type=int
                )

                n = request.form.get(
                    "name",
                    ""
                ).strip()

                r = request.form.get(
                    "role",
                    ""
                ).strip()

                bio = request.form.get(
                    "bio",
                    ""
                ).strip()

                if not mid or not n:

                    raise ValueError(
                        "Minister information is incomplete."
                    )

                f = request.files.get(
                    "image"
                )

                if f and f.filename:

                    img = save_image(
                        f
                    )

                    db.execute(
                        """
                        UPDATE ministers
                        SET
                            name=?,
                            role=?,
                            image=?,
                            bio=?
                        WHERE id=?
                        """,
                        (
                            n,
                            r,
                            img,
                            bio,
                            mid
                        )
                    )

                else:

                    db.execute(
                        """
                        UPDATE ministers
                        SET
                            name=?,
                            role=?,
                            bio=?
                        WHERE id=?
                        """,
                        (
                            n,
                            r,
                            bio,
                            mid
                        )
                    )


            # =================================================
            # DELETE MINISTER
            # =================================================

            elif action == "delete_minister":

                minister_id = request.form.get(
                    "minister_id",
                    type=int
                )

                if minister_id:

                    db.execute(
                        """
                        DELETE FROM ministers
                        WHERE id=?
                        """,
                        (minister_id,)
                    )


            # =================================================
            # ADD GALLERY
            # =================================================

            elif action == "add_gallery":

                for f in request.files.getlist(
                    "images"
                ):

                    if f and f.filename:

                        image_path = save_image(
                            f,
                            "Gallery"
                        )

                        db.execute(
                            """
                            INSERT INTO gallery (
                                image_path
                            )
                            VALUES (?)
                            """,
                            (image_path,)
                        )


            # =================================================
            # DELETE GALLERY
            # =================================================

            elif action == "delete_gallery":

                image_id = request.form.get(
                    "image_id",
                    type=int
                )

                if image_id:

                    db.execute(
                        """
                        DELETE FROM gallery
                        WHERE id=?
                        """,
                        (image_id,)
                    )


            # =================================================
            # DELETE CONTACT
            # =================================================

            elif action == "delete_contact":

                contact_id = request.form.get(
                    "contact_id",
                    type=int
                )

                if contact_id:

                    db.execute(
                        """
                        DELETE FROM contact_messages
                        WHERE id=?
                        """,
                        (contact_id,)
                    )


            # =================================================
            # DELETE VOLUNTEER
            # =================================================

            elif action == "delete_volunteer":

                volunteer_id = request.form.get(
                    "volunteer_id",
                    type=int
                )

                if volunteer_id:

                    db.execute(
                        """
                        DELETE FROM volunteer_applications
                        WHERE id=?
                        """,
                        (volunteer_id,)
                    )


            # =================================================
            # DELETE NEWSLETTER
            # =================================================

            elif action == "delete_newsletter":

                subscriber_id = request.form.get(
                    "subscriber_id",
                    type=int
                )

                if subscriber_id:

                    db.execute(
                        """
                        DELETE FROM newsletter_subscribers
                        WHERE id=?
                        """,
                        (subscriber_id,)
                    )


            # =================================================
            # BROADCAST NOTIFICATION
            # =================================================

            elif action == "send_broadcast_notification":

                title = request.form.get(
                    "notification_title",
                    ""
                ).strip()

                message = request.form.get(
                    "notification_message",
                    ""
                ).strip()

                audience = request.form.get(
                    "notification_audience",
                    "visitor"
                ).strip() or "visitor"

                if not title or not message:

                    raise ValueError(
                        "Please provide both a title and a message for the notification."
                    )

                if audience not in {
                    "visitor",
                    "admin"
                }:

                    raise ValueError(
                        "Invalid notification audience."
                    )

                sent = send_push_notification(
                    title,
                    message,
                    url_for(
                        "index",
                        _external=True
                    ),
                    audience=audience
                )

                flash(
                    f"Notification sent to {sent} subscribed users."
                )


            db.commit()

            flash(
                "Changes Saved Successfully!"
            )

        except Exception as error:

            db.rollback()

            flash(
                f"Error: {str(error)}"
            )

        return redirect(
            url_for("admin")
        )


    # ========================================================
    # DASHBOARD COUNTS
    # ========================================================

    volunteer_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM volunteer_applications
        """
    ).fetchone()

    contact_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM contact_messages
        """
    ).fetchone()

    newsletter_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM newsletter_subscribers
        """
    ).fetchone()


    counts = {
        "volunteers": volunteer_count["count"],
        "contacts": contact_count["count"],
        "newsletter": newsletter_count["count"]
    }


    # ========================================================
    # DASHBOARD
    # ========================================================

    return render_template(
        "admin.html",

        hero=db.execute(
            """
            SELECT *
            FROM hero
            LIMIT 1
            """
        ).fetchone(),

        upcoming_event=db.execute(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone(),

        ministers=db.execute(
            """
            SELECT *
            FROM ministers
            ORDER BY id ASC
            """
        ).fetchall(),

        gallery_images=db.execute(
            """
            SELECT *
            FROM gallery
            ORDER BY id DESC
            """
        ).fetchall(),

        contact_messages=db.execute(
            """
            SELECT *
            FROM contact_messages
            ORDER BY id DESC
            """
        ).fetchall(),

        volunteer_applications=db.execute(
            """
            SELECT *
            FROM volunteer_applications
            ORDER BY id DESC
            """
        ).fetchall(),

        newsletter_subscribers=db.execute(
            """
            SELECT *
            FROM newsletter_subscribers
            ORDER BY id DESC
            """
        ).fetchall(),

        submission_counts_json=json.dumps(
            counts
        ),

        vapid_public_key=os.environ.get(
            "VAPID_PUBLIC_KEY",
            ""
        )
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    try:

        db = get_db()

        result = db.execute(
            """
            SELECT 1 AS ok
            """
        ).fetchone()

        if result and result["ok"] == 1:

            return jsonify({
                "status": "ok",
                "database": "connected"
            }), 200

        return jsonify({
            "status": "error",
            "database": "failed"
        }), 500

    except Exception as error:

        return jsonify({
            "status": "error",
            "database": "failed",
            "message": str(error)
        }), 500


@app.route('/robots.txt')
def robots():
    robots_content = "User-agent: *\nAllow: /\nSitemap: https://ecwalagoswestdcc.org/sitemap.xml"
    return Response(robots_content, mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    base_url = "https://ecwalagoswestdcc.org"
    urls = [
        {'loc': f"{base_url}/", 'lastmod': today, 'priority': '1.0'},
        {'loc': f"{base_url}/events", 'lastmod': today, 'priority': '0.9'},
        {'loc': f"{base_url}/about", 'lastmod': today, 'priority': '0.8'},
        {'loc': f"{base_url}/gallery", 'lastmod': today, 'priority': '0.8'},
        {'loc': f"{base_url}/contact", 'lastmod': today, 'priority': '0.7'},
        {'loc': f"{base_url}/volunteer", 'lastmod': today, 'priority': '0.7'},
    ]
    
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in urls:
        xml.append(f"  <url>\n    <loc>{u['loc']}</loc>\n    <lastmod>{u['lastmod']}</lastmod>\n    <priority>{u['priority']}</priority>\n  </url>")
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(
        host=os.environ.get(
            "HOST",
            "127.0.0.1"
        ),
        port=int(
            os.environ.get(
                "PORT",
                "5002"
            )
        ),
        debug=(
            os.environ.get(
                "FLASK_DEBUG",
                "0"
            ) == "1"
        ),
        use_reloader=False
    )
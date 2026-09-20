from flask import Flask, render_template, request, redirect, url_for, g, session, flash, jsonify, send_from_directory, abort
import sqlite3
import os
import json
import re
import secrets
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

load_dotenv()

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['DATABASE'] = os.path.join(BASE_DIR, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'images')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE') == '1'
app.config['MAX_FORM_MEMORY_SIZE'] = 512 * 1024
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 if os.environ.get('FLASK_DEBUG') == '1' else 31536000
app.config['TEMPLATES_AUTO_RELOAD'] = os.environ.get('FLASK_DEBUG') == '1'

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 10
rate_limit_store = {}


def ensure_column(db, table, column, definition):
    columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
    if column not in columns:
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery'), exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def protect_requests():
    if request.method == 'POST':
        now = monotonic()
        address = request.remote_addr or 'unknown'
        recent = [stamp for stamp in rate_limit_store.get(address, []) if now - stamp < RATE_LIMIT_WINDOW]
        if len(recent) >= RATE_LIMIT_MAX_REQUESTS:
            return jsonify(success=False, message='Too many requests. Please try again shortly.'), 429
        recent.append(now)
        rate_limit_store[address] = recent

        session_token = session.get('_csrf_token')
        supplied = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
        if not session_token or supplied != session_token:
            return jsonify(success=False, message='Invalid security token.'), 400

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
        db.executescript('''
            CREATE TABLE IF NOT EXISTS contact_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, subject TEXT, message TEXT, submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS volunteer_applications (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, email TEXT, phone TEXT, age TEXT, team TEXT, submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS newsletter_subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, event_date TEXT, flyer_image TEXT);
            CREATE TABLE IF NOT EXISTS gallery (id INTEGER PRIMARY KEY AUTOINCREMENT, image_path TEXT);
            CREATE TABLE IF NOT EXISTS ministers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, role TEXT, image TEXT);
            CREATE TABLE IF NOT EXISTS hero (id INTEGER PRIMARY KEY AUTOINCREMENT, main_title TEXT, subtitle TEXT, media_path TEXT, livestream_url TEXT);
            CREATE TABLE IF NOT EXISTS push_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT NOT NULL UNIQUE, p256dh TEXT NOT NULL, auth TEXT NOT NULL, audience TEXT NOT NULL DEFAULT 'visitor', active INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS site_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS first_image (id INTEGER PRIMARY KEY AUTOINCREMENT, image_path TEXT)
        ''')
        ensure_column(db, 'events', 'slug', 'TEXT')
        ensure_column(db, 'events', 'edition_year', 'INTEGER')
        ensure_column(db, 'events', 'parent_event_id', 'INTEGER')
        ensure_column(db, 'events', 'event_type', "TEXT DEFAULT 'concert'")
        ensure_column(db, 'events', 'month', 'TEXT')
        ensure_column(db, 'events', 'day_label', 'TEXT')
        ensure_column(db, 'events', 'start_time', 'TEXT')
        ensure_column(db, 'events', 'end_time', 'TEXT')
        ensure_column(db, 'events', 'venue', 'TEXT')
        ensure_column(db, 'events', 'description', 'TEXT')
        ensure_column(db, 'events', 'is_published', 'INTEGER DEFAULT 1')
        ensure_column(db, 'events', 'registration_enabled', 'INTEGER DEFAULT 0')
        ensure_column(db, 'events', 'published_at', 'TIMESTAMP')
        ensure_column(db, 'volunteer_applications', 'skills', 'TEXT')
        ensure_column(db, 'volunteer_applications', 'availability', 'TEXT')
        ensure_column(db, 'volunteer_applications', 'experience', 'TEXT')
        ensure_column(db, 'volunteer_applications', 'message', 'TEXT')
        ensure_column(db, 'ministers', 'bio', 'TEXT')
        db.execute("UPDATE events SET slug = lower(replace(title, ' ', '-')) WHERE slug IS NULL")
        hero_columns = {row[1] for row in db.execute('PRAGMA table_info(hero)')}
        if 'livestream_url' not in hero_columns:
            db.execute('ALTER TABLE hero ADD COLUMN livestream_url TEXT')
        if not db.execute('SELECT id FROM hero LIMIT 1').fetchone():
            db.execute('INSERT INTO hero (main_title, subtitle, media_path, livestream_url) VALUES (?, ?, ?, ?)', ('WELCOME TO ECWA GLORY', 'Raise your heart and voice in praise.', '', 'https://www.youtube.com/watch?v=LMLp-aBI0BE'))
        db.commit()
    return db


def normalize_livestream_url(value):
    raw = (value or '').strip()
    if not raw:
        return 'https://www.youtube.com/embed/LMLp-aBI0BE'
    if raw.startswith('https://www.youtube.com/embed/') or raw.startswith('http://www.youtube.com/embed/') or raw.startswith('https://youtube.com/embed/') or raw.startswith('https://www.youtube.com/live/') or raw.startswith('https://youtube.com/live/'):
        return raw
    if 'youtube.com/watch?v=' in raw:
        video_id = re.search(r'[?&]v=([A-Za-z0-9_-]+)', raw)
        return f"https://www.youtube.com/embed/{video_id.group(1)}" if video_id else raw
    if 'youtu.be/' in raw:
        video_id = re.search(r'youtu\.be/([A-Za-z0-9_-]+)', raw)
        return f"https://www.youtube.com/embed/{video_id.group(1)}" if video_id else raw
    return raw


def get_livestream_link(value):
    raw = (value or '').strip()
    if not raw:
        return 'https://www.youtube.com/live/LMLp-aBI0BE'
    return raw


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_image(upload, subdirectory=''):
    if not upload or not upload.filename:
        return None
    if not allowed_image(upload.filename):
        raise ValueError('Only JPG, JPEG, PNG, GIF, and WebP images are allowed.')
    filename = secure_filename(upload.filename)
    if not filename:
        raise ValueError('The uploaded image has an invalid filename.')
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], subdirectory)
    os.makedirs(target_dir, exist_ok=True)
    upload.save(os.path.join(target_dir, filename))
    return os.path.join(subdirectory, filename).replace('\\', '/')


def required_form_values(fields):
    values = {field: request.form.get(field, '').strip() for field in fields}
    missing = [field for field, value in values.items() if not value]
    if missing:
        raise ValueError('Please complete all required fields.')
    return values


def event_slug(title, event_id=None):
    value = re.sub(r'[^a-z0-9]+', '-', (title or '').lower()).strip('-') or 'event'
    return f'{value}-{event_id}' if event_id else value


def event_status_label(event_date):
    if not event_date:
        return 'Upcoming'
    date_text = (event_date or '').strip()
    for fmt in ('%b %d, %Y', '%B %d, %Y', '%d %B %Y', '%Y-%m-%d', '%b %d %Y', '%B %d %Y', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            parsed = datetime.strptime(date_text, fmt).date()
            return 'Completed' if parsed < datetime.utcnow().date() else 'Upcoming'
        except ValueError:
            continue
    return 'Upcoming'


def send_push_notification(title, body, url, audience='visitor'):
    private_key = os.environ.get('VAPID_PRIVATE_KEY')
    subject = os.environ.get('VAPID_SUBJECT')
    if not webpush or not private_key or not subject:
        return 0
    db = get_db()
    subscriptions = db.execute(
        'SELECT * FROM push_subscriptions WHERE audience=? AND active=1', (audience,)
    ).fetchall()
    payload = json.dumps({'title': title, 'body': body, 'url': url})
    sent = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': subscription['endpoint'],
                    'keys': {'p256dh': subscription['p256dh'], 'auth': subscription['auth']},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={'sub': subject},
            )
            sent += 1
        except WebPushException as error:
            if getattr(error, 'response', None) is not None and error.response.status_code in {404, 410}:
                db.execute('UPDATE push_subscriptions SET active=0 WHERE id=?', (subscription['id'],))
    db.commit()
    return sent

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    return response

@app.route('/')
def index():
    db = get_db()
    hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
    ministers = db.execute('SELECT * FROM ministers').fetchall()
    upcoming_event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
    livestream_url = hero['livestream_url'] if hero and 'livestream_url' in hero.keys() else ''
    return render_template('index.html', hero=hero, ministers=ministers, upcoming_event=upcoming_event, livestream_embed_url=normalize_livestream_url(livestream_url), livestream_link_url=get_livestream_link(livestream_url))

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/api/check_messages')
@login_required
def check_messages():
    last_id = request.args.get('last_id', 0, type=int)
    db = get_db()
    new_msgs = db.execute('SELECT id, name, subject FROM contact_messages WHERE id > ? ORDER BY id ASC', (last_id,)).fetchall()
    return jsonify([dict(m) for m in new_msgs])

@app.route('/about')
def about(): return render_template('About.html')

@app.route('/gallery_page')
def gallery_page():
    db = get_db()
    images = db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    return render_template('gallery.html', images=images)


@app.route('/gallery')
def gallery():
    return redirect(url_for('gallery_page'))


@app.route('/events')
def events():
    event_rows = get_db().execute(
        'SELECT * FROM events WHERE COALESCE(is_published, 1)=1 ORDER BY event_date ASC, id ASC'
    ).fetchall()
    safe_rows = []
    for event in event_rows:
        event_payload = dict(event)
        event_payload['status_label'] = event_status_label(event['event_date'])
        safe_rows.append(event_payload)
    return render_template('events.html', events=safe_rows)


@app.route('/events/<slug>')
def event_detail(slug):
    event = get_db().execute(
        'SELECT * FROM events WHERE slug=? AND COALESCE(is_published, 1)=1 LIMIT 1',
        (slug,)
    ).fetchone()
    if event is None:
        abort(404)
    return render_template('event_detail.html', event=event)


@app.route('/notifications')
def notifications():
    return render_template('notifications.html', vapid_public_key=os.environ.get('VAPID_PUBLIC_KEY', ''))


@app.post('/api/push/subscribe')
def subscribe_push():
    payload = request.get_json(silent=True) or {}
    keys = payload.get('keys') or {}
    endpoint = str(payload.get('endpoint', '')).strip()
    p256dh = str(keys.get('p256dh', '')).strip()
    auth = str(keys.get('auth', '')).strip()
    audience = str(payload.get('audience', 'visitor')).strip() or 'visitor'
    if not endpoint or not p256dh or not auth or audience not in {'visitor', 'admin'}:
        return jsonify(success=False, message='Invalid push subscription.'), 400
    if audience == 'admin' and 'admin_logged_in' not in session:
        return jsonify(success=False, message='Admin authentication required.'), 403
    db = get_db()
    db.execute('''
        INSERT INTO push_subscriptions (endpoint, p256dh, auth, audience, active, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth,
        audience=excluded.audience, active=1, updated_at=CURRENT_TIMESTAMP
    ''', (endpoint, p256dh, auth, audience))
    db.commit()
    return jsonify(success=True)


@app.post('/api/push/unsubscribe')
def unsubscribe_push():
    payload = request.get_json(silent=True) or {}
    endpoint = str(payload.get('endpoint', '')).strip()
    if not endpoint:
        return jsonify(success=False, message='Subscription endpoint is required.'), 400
    db = get_db()
    db.execute('UPDATE push_subscriptions SET active=0, updated_at=CURRENT_TIMESTAMP WHERE endpoint=?', (endpoint,))
    db.commit()
    return jsonify(success=True)


@app.route('/admin/events', methods=['GET', 'POST'])
@login_required
def admin_events():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action', 'create')
        event_id = request.form.get('event_id', type=int)
        try:
            if action == 'delete' and event_id:
                db.execute('DELETE FROM events WHERE id=?', (event_id,))
            elif action in {'create', 'update'}:
                values = required_form_values(['title', 'event_date', 'event_type'])
                existing = db.execute('SELECT is_published FROM events WHERE id=?', (event_id,)).fetchone() if event_id else None
                published = 1 if request.form.get('is_published') == 'on' else 0
                fields = (
                    values['title'], event_slug(values['title'], event_id), request.form.get('edition_year', type=int),
                    request.form.get('parent_event_id', type=int), values['event_type'], request.form.get('month', '').strip(),
                    request.form.get('day_label', '').strip(), values['event_date'], request.form.get('start_time', '').strip(),
                    request.form.get('end_time', '').strip(), request.form.get('venue', '').strip(), request.form.get('description', '').strip(),
                    published, 1 if request.form.get('registration_enabled') == 'on' else 0,
                )
                if action == 'create':
                    cursor = db.execute('''INSERT INTO events (title, slug, edition_year, parent_event_id, event_type, month, day_label, event_date, start_time, end_time, venue, description, is_published, registration_enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', fields)
                    event_id = cursor.lastrowid
                else:
                    db.execute('''UPDATE events SET title=?, slug=?, edition_year=?, parent_event_id=?, event_type=?, month=?, day_label=?, event_date=?, start_time=?, end_time=?, venue=?, description=?, is_published=?, registration_enabled=? WHERE id=?''', fields + (event_id,))
                if published and (existing is None or not existing['is_published']):
                    db.execute('UPDATE events SET published_at=COALESCE(published_at, CURRENT_TIMESTAMP) WHERE id=?', (event_id,))
                    send_push_notification(values['title'], request.form.get('description', '').strip()[:160], url_for('event_detail', slug=event_slug(values['title'], event_id), _external=True))
            db.commit()
            flash('Event changes saved.')
        except ValueError as error:
            flash(str(error))
        return redirect(url_for('admin_events'))
    event_rows = db.execute('SELECT * FROM events ORDER BY edition_year DESC, event_date ASC, id ASC').fetchall()
    return render_template('admin_events.html', events=event_rows)


@app.route('/admin/gallery', methods=['GET', 'POST'])
@login_required
def admin_gallery():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'upload':
            for upload in request.files.getlist('images'):
                if upload and upload.filename:
                    image_path = save_image(upload, 'Gallery')
                    db.execute('INSERT INTO gallery (image_path) VALUES (?)', (image_path,))
        elif action == 'delete':
            db.execute('DELETE FROM gallery WHERE id=?', (request.form.get('image_id', type=int),))
        db.commit()
        return redirect(url_for('admin_gallery'))
    images = db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    return render_template('admin_gallery.html', images=images)


@app.route('/admin/volunteers/<int:volunteer_id>')
@login_required
def volunteer_detail(volunteer_id):
    volunteer_application = get_db().execute(
        'SELECT * FROM volunteer_applications WHERE id=?', (volunteer_id,)
    ).fetchone()
    if volunteer_application is None:
        abort(404)
    return render_template('volunteer_detail.html', volunteer=volunteer_application)

@app.route('/support')
def support(): return render_template('support.html')

@app.route('/volunteer', methods=['GET', 'POST'])
def volunteer():
    if request.method == 'POST':
        try:
            values = required_form_values(['full_name', 'email', 'phone', 'team'])
            if '@' not in values['email']:
                raise ValueError('Please enter a valid email address.')
            db = get_db()
            db.execute(
                '''INSERT INTO volunteer_applications
                   (full_name, email, phone, age, team, skills, availability, experience, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    values['full_name'], values['email'], values['phone'],
                    request.form.get('age', '').strip(), values['team'],
                    request.form.get('skills', '').strip(), request.form.get('availability', '').strip(),
                    request.form.get('experience', '').strip(), request.form.get('message', '').strip(),
                ),
            )
            db.commit()
            send_push_notification('New volunteer application', f"{values['full_name']} applied for the {values['team']} team.", url_for('admin', _external=True), audience='admin')
            return redirect(url_for('thank_you', type='volunteer'))
        except ValueError as error:
            flash(str(error))
    return render_template('volunteer.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            values = required_form_values(['name', 'email', 'message'])
            if '@' not in values['email']:
                raise ValueError('Please enter a valid email address.')
            db = get_db()
            db.execute('INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
                       (values['name'], values['email'], request.form.get('subject', '').strip(), values['message']))
            db.commit()
            send_push_notification('New visitor message', f"{values['name']} sent a new message.", url_for('admin', _external=True), audience='admin')
            return redirect(url_for('thank_you', type='contact'))
        except ValueError as error:
            return render_template('contact.html', error=str(error)), 400
    return render_template('contact.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email')
    if email:
        db = get_db()
        db.execute('INSERT INTO newsletter_subscribers (email) VALUES (?)', (email,))
        db.commit()
    return redirect(url_for('thank_you', type='newsletter'))


    return jsonify({"success": True, "message": "Application submitted successfully!"})


@app.route('/thank-you')
def thank_you():
    t = request.args.get('type')
    msg = "Submission Successful!"
    if t == 'volunteer': msg = "Thank you for volunteering!"
    elif t == 'newsletter': msg = "Thank you for subscribing!"
    return render_template('thank-you.html', message=msg)

@app.route('/frank.html')
def frank(): return render_template('frank.html')
@app.route('/kaywonder.html')
def kaywonder(): return render_template('kaywonder.html')
@app.route('/akinyemi.html')
def akinyemi(): return render_template('akinyemi.html')
@app.route('/babatunde.html')
def babatunde(): return render_template('babatunde.html')
@app.route('/pelumi.html')
def pelumi(): return render_template('pelumi.html')


@app.route('/minister/<int:minister_id>')
def minister_profile(minister_id):
    minister = get_db().execute('SELECT * FROM ministers WHERE id=?', (minister_id,)).fetchone()
    if minister is None:
        abort(404)
    return render_template('minister-profile.html', minister=minister)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        password_valid = bool(ADMIN_PASSWORD_HASH and check_password_hash(ADMIN_PASSWORD_HASH, password))
        password_valid = password_valid or bool(ADMIN_PASSWORD and secrets.compare_digest(password, ADMIN_PASSWORD))
        if password_valid:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid Admin Password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('admin_action')
        try:
            if action == 'update_hero':
                livestream_url = request.form.get('livestream_url', '').strip()
                db.execute('UPDATE hero SET main_title=?, subtitle=?, livestream_url=? WHERE id=(SELECT id FROM hero LIMIT 1)',
                           (request.form.get('main_title'), request.form.get('subtitle'), livestream_url))
            elif action == 'update_event':
                title, date = request.form.get('title'), request.form.get('event_date')
                file = request.files.get('flyer_image')
                event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
                img = event['flyer_image'] if event else 'default.jpg'
                if file and file.filename:
                    img = save_image(file)
                if event: db.execute('UPDATE events SET title=?, event_date=?, flyer_image=? WHERE id=?', (title, date, img, event['id']))
                else: db.execute('INSERT INTO events (title, event_date, flyer_image) VALUES (?, ?, ?)', (title, date, img))
            elif action == 'add_minister':
                n, r, bio, f = request.form.get('name'), request.form.get('role'), request.form.get('bio', '').strip(), request.files.get('image')
                img = save_image(f) if f and f.filename else 'default.jpg'
                db.execute('INSERT INTO ministers (name, role, image, bio) VALUES (?, ?, ?, ?)', (n, r, img, bio))
            elif action == 'edit_minister':
                mid, n, r, bio, f = request.form.get('minister_id'), request.form.get('name'), request.form.get('role'), request.form.get('bio', '').strip(), request.files.get('image')
                if f and f.filename:
                    img = save_image(f)
                    db.execute('UPDATE ministers SET name=?, role=?, image=?, bio=? WHERE id=?', (n, r, img, bio, mid))
                else: db.execute('UPDATE ministers SET name=?, role=?, bio=? WHERE id=?', (n, r, bio, mid))
            elif action == 'delete_minister':
                db.execute('DELETE FROM ministers WHERE id=?', (request.form.get('minister_id'),))
            elif action == 'add'
            elif action == 'add_gallery':
                for f in request.files.getlist('images'):
                    if f and f.filename:
                        image_path = save_image(f, 'Gallery')
                        db.execute('INSERT INTO gallery (image_path) VALUES (?)', (image_path,))
            elif action == 'delete_gallery':
                db.execute('DELETE FROM gallery WHERE id=?', (request.form.get('image_id'),))
            elif action == 'delete_contact': db.execute('DELETE FROM contact_messages WHERE id=?', (request.form.get('contact_id'),))
            elif action == 'delete_volunteer': db.execute('DELETE FROM volunteer_applications WHERE id=?', (request.form.get('volunteer_id'),))
            elif action == 'delete_newsletter': db.execute('DELETE FROM newsletter_subscribers WHERE id=?', (request.form.get('subscriber_id'),))
            elif action == 'send_broadcast_notification':
                title = request.form.get('notification_title', '').strip()
                message = request.form.get('notification_message', '').strip()
                audience = request.form.get('notification_audience', 'visitor').strip() or 'visitor'
                if not title or not message:
                    raise ValueError('Please provide both a title and a message for the notification.')
                if audience not in {'visitor', 'admin'}:
                    raise ValueError('Invalid notification audience.')
                send_push_notification(title, message, url_for('index', _external=True), audience=audience)
                flash('Notification sent to subscribed users.')
            db.commit()
            flash('Changes Saved Successfully!')
        except Exception as e: flash(f'Error: {str(e)}')
        return redirect(url_for('admin'))

    counts = {
        'volunteers': db.execute('SELECT COUNT(*) FROM volunteer_applications').fetchone()[0],
        'contacts': db.execute('SELECT COUNT(*) FROM contact_messages').fetchone()[0],
        'newsletter': db.execute('SELECT COUNT(*) FROM newsletter_subscribers').fetchone()[0]
    }
    return render_template('admin.html',
        hero=db.execute('SELECT * FROM hero LIMIT 1').fetchone(),
        upcoming_event=db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone(),
        ministers=db.execute('SELECT * FROM ministers').fetchall(),
        gallery_images=db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall(),
        contact_messages=db.execute('SELECT * FROM contact_messages ORDER BY id DESC').fetchall(),
        volunteer_applications=db.execute('SELECT * FROM volunteer_applications ORDER BY id DESC').fetchall(),
        newsletter_subscribers=db.execute('SELECT * FROM newsletter_subscribers ORDER BY id DESC').fetchall(),
        submission_counts_json=json.dumps(counts),
        vapid_public_key=os.environ.get('VAPID_PUBLIC_KEY', ''))

if __name__ == '__main__':
    app.run(
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '5002')),
        debug=os.environ.get('FLASK_DEBUG') == '1',
        use_reloader=False,
    )

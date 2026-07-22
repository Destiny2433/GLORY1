from flask import Flask, render_template, request, redirect, url_for, g, session, flash, jsonify, send_from_directory
import sqlite3
import os
import json
import re
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['DATABASE'] = os.path.join(BASE_DIR, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'images')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'glory_secret_key_2025_prod_final')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'glory123')
GIT 
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery'), exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
        ''')
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

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

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

@app.route('/support')
def support(): return render_template('support.html')

@app.route('/volunteer', methods=['GET', 'POST'])
def volunteer():
    if request.method == 'POST':
        db = get_db()
        db.execute('INSERT INTO volunteer_applications (full_name, email, phone, age, team) VALUES (?, ?, ?, ?, ?)',
                   (request.form.get('full_name'), request.form.get('email'), request.form.get('phone'), request.form.get('age'), request.form.get('team')))
        db.commit()
        return redirect(url_for('thank_you', type='volunteer'))
    return render_template('volunteer.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        db = get_db()
        db.execute('INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
                   (request.form.get('name'), request.form.get('email'), request.form.get('subject'), request.form.get('message')))
        db.commit()
        return redirect(url_for('thank_you', type='contact'))
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
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
                    img = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                if event: db.execute('UPDATE events SET title=?, event_date=?, flyer_image=? WHERE id=?', (title, date, img, event['id']))
                else: db.execute('INSERT INTO events (title, event_date, flyer_image) VALUES (?, ?, ?)', (title, date, img))
            elif action == 'add_minister':
                n, r, f = request.form.get('name'), request.form.get('role'), request.files.get('image')
                img = secure_filename(f.filename) if f and f.filename else 'default.jpg'
                if f and f.filename: f.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                db.execute('INSERT INTO ministers (name, role, image) VALUES (?, ?, ?)', (n, r, img))
            elif action == 'edit_minister':
                mid, n, r, f = request.form.get('minister_id'), request.form.get('name'), request.form.get('role'), request.files.get('image')
                if f and f.filename:
                    img = secure_filename(f.filename)
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                    db.execute('UPDATE ministers SET name=?, role=?, image=? WHERE id=?', (n, r, img, mid))
                else: db.execute('UPDATE ministers SET name=?, role=? WHERE id=?', (n, r, mid))
            elif action == 'delete_minister':
                db.execute('DELETE FROM ministers WHERE id=?', (request.form.get('minister_id'),))
            elif action == 'add_gallery':
                for f in request.files.getlist('images'):
                    if f and f.filename:
                        fn = secure_filename(f.filename)
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery', fn))
                        db.execute('INSERT INTO gallery (image_path) VALUES (?)', ('Gallery/' + fn,))
            elif action == 'delete_gallery':
                db.execute('DELETE FROM gallery WHERE id=?', (request.form.get('image_id'),))
            elif action == 'delete_contact': db.execute('DELETE FROM contact_messages WHERE id=?', (request.form.get('contact_id'),))
            elif action == 'delete_volunteer': db.execute('DELETE FROM volunteer_applications WHERE id=?', (request.form.get('volunteer_id'),))
            elif action == 'delete_newsletter': db.execute('DELETE FROM newsletter_subscribers WHERE id=?', (request.form.get('subscriber_id'),))
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
        submission_counts_json=json.dumps(counts))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

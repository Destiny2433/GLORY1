from flask import Flask, render_template, request, redirect, url_for, g, session, flash, jsonify, send_from_directory
import sqlite3
import os
import smtplib
import json
from email.message import EmailMessage
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from functools import wraps
import traceback

load_dotenv()

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.root_path, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_key')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'glory123')

EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'okonudestiny4@gmail.com')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery'), exist_ok=True)

def create_tables_if_needed(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            age TEXT,
            team TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS newsletter_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            flyer_image TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS ministers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            image TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS hero (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_title TEXT NOT NULL,
            subtitle TEXT NOT NULL,
            media_path TEXT NOT NULL
        )
    ''')

    # Schema migration: Check if subject column exists in contact_messages
    try:
        cursor = db.execute("PRAGMA table_info(contact_messages)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'subject' not in columns:
            db.execute('ALTER TABLE contact_messages ADD COLUMN subject TEXT')
    except:
        pass

    db.commit()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
        create_tables_if_needed(db)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
    ministers = db.execute('SELECT * FROM ministers').fetchall()
    upcoming_event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
    return render_template('index.html', hero=hero, ministers=ministers, upcoming_event=upcoming_event)

@app.route('/about')
def about():
    return render_template('About.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', 'Contact Form Submission').strip()
        message = request.form.get('message', '').strip()
        if not name or not email or not message:
            error = 'Please fill in all required fields.'
        else:
            db = get_db()
            db.execute('INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
                       (name, email, subject, message))
            db.commit()
            return redirect(url_for('thank_you', type='contact'))
    return render_template('contact.html', error=error)

@app.route('/gallery')
def gallery():
    db = get_db()
    images = db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    return render_template('gallery.html', images=images)

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/volunteer', methods=['GET', 'POST'])
def volunteer():
    if request.method == 'POST':
        data = (request.form.get('full_name'), request.form.get('email'), request.form.get('phone'),
                request.form.get('age'), request.form.get('team'))
        db = get_db()
        db.execute('INSERT INTO volunteer_applications (full_name, email, phone, age, team) VALUES (?, ?, ?, ?, ?)', data)
        db.commit()
        return redirect(url_for('thank_you', type='volunteer'))
    return render_template('volunteer.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email')
    if email:
        db = get_db()
        db.execute('INSERT INTO newsletter_subscribers (email) VALUES (?)', (email,))
        db.commit()
    return redirect(url_for('thank_you', type='newsletter'))

@app.route('/thank-you')
def thank_you():
    t = request.args.get('type')
    msg = "Your message has been received!"
    if t == 'volunteer': msg = "Thank you for volunteering! We will contact you soon."
    elif t == 'newsletter': msg = "Thank you for subscribing to our newsletter!"
    return render_template('thank-you.html', message=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid password')
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
        action = request.form.get('action')
        try:
            if action == 'update_event':
                title, date = request.form.get('title'), request.form.get('event_date')
                file = request.files.get('flyer_image')
                event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
                img = event['flyer_image'] if event else 'default.jpg'
                if file and file.filename:
                    img = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                if event:
                    db.execute('UPDATE events SET title=?, event_date=?, flyer_image=? WHERE id=?', (title, date, img, event['id']))
                else:
                    db.execute('INSERT INTO events (title, event_date, flyer_image) VALUES (?, ?, ?)', (title, date, img))
                flash('Event updated successfully')

            elif action == 'update_hero':
                t, s = request.form.get('main_title'), request.form.get('subtitle')
                hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
                if hero:
                    db.execute('UPDATE hero SET main_title=?, subtitle=? WHERE id=?', (t, s, hero['id']))
                else:
                    db.execute('INSERT INTO hero (main_title, subtitle, media_path) VALUES (?, ?, ?)', (t, s, ''))
                flash('Hero section updated')

            elif action == 'add_minister':
                n, r, f = request.form.get('name'), request.form.get('role'), request.files.get('image')
                img = 'default.jpg'
                if f and f.filename:
                    img = secure_filename(f.filename)
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                db.execute('INSERT INTO ministers (name, role, image) VALUES (?, ?, ?)', (n, r, img))
                flash('Minister added')

            elif action == 'edit_minister':
                mid, n, r, f = request.form.get('minister_id'), request.form.get('name'), request.form.get('role'), request.files.get('image')
                if f and f.filename:
                    img = secure_filename(f.filename)
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], img))
                    db.execute('UPDATE ministers SET name=?, role=?, image=? WHERE id=?', (n, r, img, mid))
                else:
                    db.execute('UPDATE ministers SET name=?, role=? WHERE id=?', (n, r, mid))
                flash('Minister updated')

            elif action == 'delete_minister':
                db.execute('DELETE FROM ministers WHERE id=?', (request.form.get('minister_id'),))
                flash('Minister deleted')

            elif action == 'add_gallery':
                for f in request.files.getlist('images'):
                    if f and f.filename:
                        fn = secure_filename(f.filename)
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery', fn))
                        db.execute('INSERT INTO gallery (image_path) VALUES (?)', ('Gallery/' + fn,))
                flash('Gallery updated')

            elif action == 'delete_gallery':
                db.execute('DELETE FROM gallery WHERE id=?', (request.form.get('image_id'),))
                flash('Image removed')

            elif action == 'delete_contact':
                db.execute('DELETE FROM contact_messages WHERE id=?', (request.form.get('contact_id'),))
            elif action == 'delete_volunteer':
                db.execute('DELETE FROM volunteer_applications WHERE id=?', (request.form.get('volunteer_id'),))
            elif action == 'delete_newsletter':
                db.execute('DELETE FROM newsletter_subscribers WHERE id=?', (request.form.get('subscriber_id'),))

            db.commit()
        except Exception as e:
            flash(f'Error: {str(e)}')
        return redirect(url_for('admin'))

    # Fetch data for display
    hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
    upcoming_event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
    ministers = db.execute('SELECT * FROM ministers').fetchall()
    gallery_images = db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    contact_messages = db.execute('SELECT * FROM contact_messages ORDER BY id DESC').fetchall()
    volunteer_applications = db.execute('SELECT * FROM volunteer_applications ORDER BY id DESC').fetchall()
    newsletter_subscribers = db.execute('SELECT * FROM newsletter_subscribers ORDER BY id DESC').fetchall()

    submission_counts_json = json.dumps({
        'volunteers': len(volunteer_applications),
        'contacts': len(contact_messages),
        'newsletter': len(newsletter_subscribers)
    })

    return render_template('admin.html',
        hero=hero,
        upcoming_event=upcoming_event,
        ministers=ministers,
        gallery_images=gallery_images,
        contact_messages=contact_messages,
        volunteer_applications=volunteer_applications,
        newsletter_subscribers=newsletter_subscribers,
        submission_counts_json=submission_counts_json
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

from flask import Flask, render_template, request, redirect, url_for, g, session, flash, jsonify, send_from_directory
import sqlite3
import os
import smtplib
import json
from email.message import EmailMessage
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.root_path, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_key')  # production should set this

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

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


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
    db.commit()


def ensure_contact_messages_schema(db):
    try:
        columns = [row['name'] for row in db.execute("PRAGMA table_info(contact_messages)").fetchall()]
        if 'subject' not in columns:
            db.execute('ALTER TABLE contact_messages ADD COLUMN subject TEXT')
            db.commit()
    except sqlite3.OperationalError:
        pass


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
        create_tables_if_needed(db)
        ensure_contact_messages_schema(db)
    return db



def send_email(subject, body, from_addr, to_addr):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        app.logger.warning('SMTP credentials are not configured; saving email to sent_emails.log for inspection.')
        try:
            with open('sent_emails.log', 'a', encoding='utf-8') as f:
                f.write('---\n')
                f.write(f'To: {to_addr}\n')
                f.write(f'From: {from_addr}\n')
                f.write(f'Subject: {subject}\n\n')
                f.write(body + '\n\n')
        except Exception as e:
            app.logger.error(f'Failed to write email log: {e}')
        return True

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        app.logger.error(f'Email send failed: {e}')
        return False

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
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        subject = request.form.get('subject') or 'Contact Form Submission'
        message = (request.form.get('message') or '').strip()

        if not name or not email or not message:
            error = 'Please provide your name, email, and message before sending.'
        else:
            try:
                db = get_db()
                db.execute(
                    'INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
                    (name, email, subject, message)
                )
                db.commit()
            except Exception as exc:
                app.logger.error(f'Contact form DB save failed: {exc}')
                try:
                    error_log_path = os.path.join(app.root_path, 'contact_error.log')
                    with open(error_log_path, 'a', encoding='utf-8') as error_file:
                        error_file.write('=== Contact form error ===\n')
                        error_file.write(f'Name: {name}\nEmail: {email}\nSubject: {subject}\nMessage: {message}\n')
                        error_file.write(f'Exception: {exc}\n')
                        error_file.write('\n')
                except Exception as log_exc:
                    app.logger.error(f'Could not write contact_error.log: {log_exc}')
                error = 'Unable to save your message right now. Please try again later.'

        if not error:
            email_subject = f'Website Contact: {subject}'

            email_body = (

                f'Contact form submitted by {name}\n'
                f'Email: {email}\n'
                f'Subject: {subject}\n\n'
                f'Message:\n{message}\n'
            )
            # send_email(...) disabled temporarily so only admin gets email notifications
            # send_email(email_subject, email_body, SMTP_USERNAME or email, EMAIL_RECIPIENT)
            return redirect(url_for('thank_you', type='contact'))

    return render_template('contact.html', error=error, request=request)

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
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        age = request.form.get('age')
        team = request.form.get('team')

        db = get_db()
        db.execute(
            'INSERT INTO volunteer_applications (full_name, email, phone, age, team) VALUES (?, ?, ?, ?, ?)',
            (full_name, email, phone, age, team)
        )
        db.commit()

        email_subject = 'Website Volunteer Application'
        email_body = (
            f'Volunteer application submitted by {full_name}\n'
            f'Email: {email}\n'
            f'Phone: {phone}\n'
            f'Age: {age or "N/A"}\n'
            f'Team: {team}\n'
        )
        send_email(email_subject, email_body, SMTP_USERNAME or email, EMAIL_RECIPIENT)
        return redirect(url_for('thank_you', type='volunteer'))
    return render_template('volunteer.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email')

    db = get_db()
    db.execute(
        'INSERT INTO newsletter_subscribers (email) VALUES (?)',
        (email,)
    )
    db.commit()

    email_subject = 'Website Newsletter Signup'
    email_body = f'Newsletter signup submitted with email: {email}\n'
    send_email(email_subject, email_body, SMTP_USERNAME or email, EMAIL_RECIPIENT)
    return redirect(url_for('thank_you', type='newsletter'))

@app.route('/thank-you')
def thank_you():
    message_type = request.args.get('type', 'default')
    if message_type == 'volunteer':
        message = "Thank you for volunteering! We have received your application and will get back to you soon."
    elif message_type == 'newsletter':
        message = "Thank you for subscribing to our newsletter! You will receive updates soon."
    else:
        message = "Your message has been sent successfully. We'll get back to you soon!"
    return render_template('thank-you.html', message=message)


@app.route('/frank.html')
def frank():
    return render_template('frank.html')

@app.route('/kaywonder.html')
def kaywonder():
    return render_template('kaywonder.html')

@app.route('/akinyemi.html')
def akinyemi():
    return render_template('akinyemi.html')

@app.route('/babatunde.html')
def babatunde():
    return render_template('babatunde.html')

@app.route('/pelumi.html')
def pelumi():
    return render_template('pelumi.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
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
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        def admin_reply(message=None):
            if is_ajax:
                return jsonify({'status': 'ok', 'action': action, 'message': message or 'Success'})
            if message:
                flash(message)
            return redirect(url_for('admin'))

        def admin_reply_error(message=None, status=400):
            if is_ajax:
                return jsonify({'status': 'error', 'action': action, 'message': message or 'Request failed'}), status
            flash(message or 'Request failed')
            return redirect(url_for('admin'))

        if not action:
            return admin_reply_error('Missing action value', 400)

        try:
            if action == 'update_event':
                title = request.form.get('title')
                date = request.form.get('event_date')
                file = request.files.get('flyer_image')
                
                event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
                flyer_filename = event['flyer_image'] if event else 'default.jpg'
                
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    flyer_filename = filename
                    
                if event:
                    db.execute('UPDATE events SET title = ?, event_date = ?, flyer_image = ? WHERE id = ?', 
                               (title, date, flyer_filename, event['id']))
                else:
                    db.execute('INSERT INTO events (title, event_date, flyer_image) VALUES (?, ?, ?)', 
                               (title, date, flyer_filename))
                db.commit()
                return admin_reply('Event updated')

            elif action == 'update_hero':
                main_title = request.form.get('main_title')
                subtitle = request.form.get('subtitle')
                
                hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
                if hero:
                    db.execute('UPDATE hero SET main_title = ?, subtitle = ? WHERE id = ?', 
                               (main_title, subtitle, hero['id']))
                else:
                    db.execute('INSERT INTO hero (main_title, subtitle, media_path) VALUES (?, ?, ?)',
                               (main_title, subtitle, ''))
                db.commit()
                return admin_reply('Hero updated')

            elif action == 'add_minister':
                name = request.form.get('name')
                role = request.form.get('role')
                file = request.files.get('image')
                image_filename = 'default.jpg'
                
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename
                    
                db.execute('INSERT INTO ministers (name, role, image) VALUES (?, ?, ?)', 
                           (name, role, image_filename))
                db.commit()
                return admin_reply('Minister added')
                
            elif action == 'edit_minister':
                minister_id = request.form.get('minister_id')
                name = request.form.get('name')
                role = request.form.get('role')
                file = request.files.get('image')
                
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    db.execute('UPDATE ministers SET name = ?, role = ?, image = ? WHERE id = ?', 
                               (name, role, filename, minister_id))
                else:
                    db.execute('UPDATE ministers SET name = ?, role = ? WHERE id = ?', 
                               (name, role, minister_id))
                db.commit()
                return admin_reply('Minister edited')

            elif action == 'delete_minister':
                minister_id = request.form.get('minister_id')
                db.execute('DELETE FROM ministers WHERE id = ?', (minister_id,))
                db.commit()
                return admin_reply('Minister deleted')
                
            elif action == 'add_gallery':
                files = request.files.getlist('images')
                for file in files:
                    if file and file.filename != '':
                        filename = secure_filename(file.filename)
                        gallery_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'Gallery')
                        os.makedirs(gallery_dir, exist_ok=True)
                        file.save(os.path.join(gallery_dir, filename))
                        db.execute('INSERT INTO gallery (image_path) VALUES (?)', ('Gallery/' + filename,))
                db.commit()
                return admin_reply('Gallery images added')
                
            elif action == 'delete_gallery':
                image_id = request.form.get('image_id')
                db.execute('DELETE FROM gallery WHERE id = ?', (image_id,))
                db.commit()
                return admin_reply('Gallery image deleted')

            elif action == 'delete_contact':
                contact_id = request.form.get('contact_id')
                db.execute('DELETE FROM contact_messages WHERE id = ?', (contact_id,))
                db.commit()
                return admin_reply('Contact deleted')

            elif action == 'delete_volunteer':
                volunteer_id = request.form.get('volunteer_id')
                db.execute('DELETE FROM volunteer_applications WHERE id = ?', (volunteer_id,))
                db.commit()
                return admin_reply('Volunteer deleted')

            elif action == 'delete_newsletter':
                subscriber_id = request.form.get('subscriber_id')
                db.execute('DELETE FROM newsletter_subscribers WHERE id = ?', (subscriber_id,))
                db.commit()
                return admin_reply('Subscriber deleted')
            else:
                return admin_reply_error(f'Unknown action: {action}', 400)
        except Exception as exc:
            app.logger.exception('Admin action failed')
            return admin_reply_error(str(exc), 500)

    # Fetch current data for the admin dashboard
    hero = db.execute('SELECT * FROM hero LIMIT 1').fetchone()
    upcoming_event = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 1').fetchone()
    ministers = db.execute('SELECT * FROM ministers').fetchall()
    gallery_images = db.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    
    # Fetch form submissions
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
                           submission_counts_json=submission_counts_json)


@app.route('/admin/submission-summary')
@login_required
def admin_submission_summary():
    db = get_db()
    contact_count = db.execute('SELECT COUNT(*) FROM contact_messages').fetchone()[0]
    volunteer_count = db.execute('SELECT COUNT(*) FROM volunteer_applications').fetchone()[0]
    newsletter_count = db.execute('SELECT COUNT(*) FROM newsletter_subscribers').fetchone()[0]

    return jsonify({
        'contact_messages': contact_count,
        'volunteer_applications': volunteer_count,
        'newsletter_subscribers': newsletter_count
    })


@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')


@app.route('/admin/fetch-submissions')
@login_required
def fetch_submissions():
    """Return HTML snippets for each submission table for real-time updates."""
    db = get_db()
    
    contact_messages = db.execute('SELECT * FROM contact_messages ORDER BY id DESC').fetchall()
    volunteer_applications = db.execute('SELECT * FROM volunteer_applications ORDER BY id DESC').fetchall()
    newsletter_subscribers = db.execute('SELECT * FROM newsletter_subscribers ORDER BY id DESC').fetchall()
    
    return jsonify({
        'contact_count': len(contact_messages),
        'volunteer_count': len(volunteer_applications),
        'newsletter_count': len(newsletter_subscribers)
    })

if __name__ == '__main__':
    # Debug must be disabled for publication.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)


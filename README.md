# ECWA Glory Concert

A Flask and SQLite website for the ECWA Glory Concert, including public event pages, volunteer and contact submissions, gallery management, an authenticated admin area, and optional Web Push notifications.

## Features

- Public home, about, events, event details, gallery, volunteer, contact, and notification pages
- Recurring event data with editions, sub-events, Vigils, publication state, venue, time, and registration flags
- Admin event management with draft and publish states
- SQLite-backed submissions and push subscriptions
- Service-worker Web Push foundation using VAPID configuration

## Development

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set a strong secret and admin password.
4. Start the app with `python app.py`.
5. Open `http://127.0.0.1:5000`.

On Windows, run the command from the project folder. If port 5000 is already in use, start with `set PORT=5001 && python app.py` and open `http://127.0.0.1:5001`.

The database is created and migrated on first application use. Do not commit `.env`, local databases, uploads, virtual environments, or cache files. Prefer `ADMIN_PASSWORD_HASH` in production; generate a Werkzeug-compatible hash with `werkzeug.security.generate_password_hash` and leave `ADMIN_PASSWORD` empty.

## Web Push

Generate a VAPID key pair and set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT`. Push requires HTTPS in production (localhost is permitted for local development). Visitors opt in from `/notifications`; published events can notify active visitor subscriptions.

## Production

Run behind a production WSGI server such as Gunicorn or Waitress. Set `FLASK_DEBUG=0`, use HTTPS, configure a persistent database and upload storage, keep secrets in the hosting provider's environment settings, and maintain database backups.

## Admin

Use `/login` with the configured `ADMIN_PASSWORD`. Change the default credentials before deployment. Event management is available at `/admin/events` after authentication.

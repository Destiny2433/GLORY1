import os
import tempfile
import sqlite3
import io
from app import app

app.config['TESTING'] = True
app.config['DATABASE'] = os.path.join(tempfile.gettempdir(), 'glory_test.db')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
try:
    os.remove(app.config['DATABASE'])
except OSError:
    pass

results = []
with app.test_client() as c:
    resp = c.post('/login', data={'password': 'glory123'}, follow_redirects=True)
    results.append(('login', resp.status_code, b'Admin Dashboard' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    resp = c.post('/admin', data={'action': 'update_hero', 'main_title': 'Test Hero', 'subtitle': 'Test Subtitle'}, follow_redirects=True)
    results.append(('update_hero', resp.status_code, b'Hero updated' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    resp = c.post('/admin', data={'action': 'update_event', 'title': 'Test Event', 'event_date': 'Tomorrow'}, follow_redirects=True)
    results.append(('update_event', resp.status_code, b'Event updated' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    data = {'action': 'add_minister', 'name': 'John Doe', 'role': 'Pastor'}
    data['image'] = (io.BytesIO(b'test'), 'minister.png')
    resp = c.post('/admin', data=data, content_type='multipart/form-data', follow_redirects=True)
    results.append(('add_minister', resp.status_code, b'Minister added' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    con = sqlite3.connect(app.config['DATABASE'])
    con.row_factory = sqlite3.Row
    minister = con.execute('SELECT * FROM ministers ORDER BY id DESC LIMIT 1').fetchone()
    mid = minister['id'] if minister else None
    con.close()
    results.append(('minister_row', mid is not None, minister['name'] if minister else None))

    if mid is not None:
        data = {'action': 'edit_minister', 'minister_id': str(mid), 'name': 'Jane Doe', 'role': 'Rev'}
        resp = c.post('/admin', data=data, follow_redirects=True)
        results.append(('edit_minister', resp.status_code, b'Minister edited' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

        resp = c.post('/admin', data={'action': 'delete_minister', 'minister_id': str(mid)}, follow_redirects=True)
        results.append(('delete_minister', resp.status_code, b'Minister deleted' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    data = {'action': 'add_gallery'}
    data['images'] = (io.BytesIO(b'test'), 'gallery.png')
    resp = c.post('/admin', data=data, content_type='multipart/form-data', follow_redirects=True)
    results.append(('add_gallery', resp.status_code, b'Gallery images added' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    con = sqlite3.connect(app.config['DATABASE'])
    con.row_factory = sqlite3.Row
    img = con.execute('SELECT * FROM gallery ORDER BY id DESC LIMIT 1').fetchone()
    iid = img['id'] if img else None
    con.close()
    results.append(('gallery_row', iid is not None, img['image_path'] if img else None))

    if iid is not None:
        resp = c.post('/admin', data={'action': 'delete_gallery', 'image_id': str(iid)}, follow_redirects=True)
        results.append(('delete_gallery', resp.status_code, b'Gallery image deleted' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    con = sqlite3.connect(app.config['DATABASE'])
    con.execute('INSERT INTO contact_messages (name,email,subject,message) VALUES (?,?,?,?)', ('A','a@a.com','s','m'))
    con.execute('INSERT INTO volunteer_applications (full_name,email,phone,age,team) VALUES (?,?,?,?,?)', ('B','b@b.com','123','30','Team'))
    con.execute('INSERT INTO newsletter_subscribers (email) VALUES (?)', ('c@c.com',))
    con.commit()
    con.close()

    resp = c.post('/admin', data={'action': 'delete_contact', 'contact_id': '1'}, follow_redirects=True)
    results.append(('delete_contact', resp.status_code, b'Contact deleted' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    resp = c.post('/admin', data={'action': 'delete_volunteer', 'volunteer_id': '1'}, follow_redirects=True)
    results.append(('delete_volunteer', resp.status_code, b'Volunteer deleted' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

    resp = c.post('/admin', data={'action': 'delete_newsletter', 'subscriber_id': '1'}, follow_redirects=True)
    results.append(('delete_newsletter', resp.status_code, b'Subscriber deleted' in resp.data, resp.data[:200].decode('utf-8', errors='replace')))

with open('admin_test_results.txt', 'w', encoding='utf-8') as out:
    for item in results:
        out.write(str(item) + '\n')
print('DONE')

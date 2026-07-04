from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    r = client.get('/admin')
    print('GET /admin', r.status_code, r.content_type)

    r2 = client.post('/admin', data={'action': 'update_hero', 'main_title': 'Test Title', 'subtitle': 'Test Subtitle'})
    print('POST /admin', r2.status_code)
    print(r2.headers.get('Content-Type'))
    print(r2.data.decode('utf-8', errors='replace')[:800])

from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    r = client.get('/admin')
    print('GET', r.status_code, r.content_type)

    r2 = client.post('/admin', data={'action': 'update_hero', 'main_title': 'test', 'subtitle': 'sub'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    print('POST', r2.status_code)
    print(r2.data.decode('utf-8', errors='replace'))
    print('is_json', r2.is_json)
    if r2.is_json:
        print('json', r2.get_json())

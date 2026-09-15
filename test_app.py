import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app import app


class GloryAppTests(unittest.TestCase):
    def setUp(self):
        self.database = os.path.join(tempfile.gettempdir(), 'glory_test_suite.db')
        try:
            os.remove(self.database)
        except FileNotFoundError:
            pass
        app.config.update(TESTING=True, DATABASE=self.database, WTF_CSRF_ENABLED=False)
        self.client = app.test_client()

    def csrf_token(self):
        response = self.client.get('/contact')
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            return session['_csrf_token']

    def test_public_pages_render(self):
        for path in ['/', '/about', '/events', '/gallery_page', '/support', '/volunteer', '/contact', '/notifications']:
            with self.subTest(path=path):
                self.assertLess(self.client.get(path).status_code, 500)

    def test_missing_page_uses_custom_404(self):
        response = self.client.get('/does-not-exist')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'We could not find that page', response.data)

    def test_public_form_requires_csrf(self):
        response = self.client.post('/contact', data={'name': 'Test', 'email': 'test@example.com', 'message': 'Hello'})
        self.assertEqual(response.status_code, 400)

    def test_contact_form_persists(self):
        token = self.csrf_token()
        response = self.client.post('/contact', data={
            '_csrf_token': token,
            'name': 'Test Visitor',
            'email': 'test@example.com',
            'subject': 'General',
            'message': 'Hello Glory',
        })
        self.assertEqual(response.status_code, 302)
        connection = sqlite3.connect(self.database)
        row = connection.execute('SELECT name, message FROM contact_messages').fetchone()
        connection.close()
        self.assertEqual(row, ('Test Visitor', 'Hello Glory'))

    def test_invalid_push_subscription_is_rejected(self):
        token = self.csrf_token()
        response = self.client.post('/api/push/subscribe', json={}, headers={'X-CSRF-Token': token})
        self.assertEqual(response.status_code, 400)

    def test_admin_broadcast_notification_sends_push(self):
        with self.client.session_transaction() as session:
            session['admin_logged_in'] = True
            session['_csrf_token'] = 'admin-token'

        with patch('app.send_push_notification', return_value=2) as mocked_send:
            response = self.client.post('/admin', data={
                '_csrf_token': 'admin-token',
                'admin_action': 'send_broadcast_notification',
                'notification_title': 'New announcement',
                'notification_message': 'The next service is this weekend.',
                'notification_audience': 'visitor',
            }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        mocked_send.assert_called_once_with('New announcement', 'The next service is this weekend.', 'http://localhost/', audience='visitor')


if __name__ == '__main__':
    unittest.main()

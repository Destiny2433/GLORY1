import os
import traceback
import app
from app import app as flask_app
print('DB_PATH=' + app.app.config['DATABASE'])
print('DB_EXISTS=' + str(os.path.exists(app.app.config['DATABASE'])))
try:
    with flask_app.test_client() as client:
        rv = client.post('/contact', data={'name':'Test User','email':'test@example.com','subject':'general','message':'Hello'}, follow_redirects=True)
        print('STATUS=' + str(rv.status_code))
        print('PATH=' + rv.request.path)
        print('FAILED_MESSAGE=' + str(b'Unable to save your message' in rv.data))
        print('BODY_START=' + rv.data.decode('utf-8','replace')[:400].replace('\n', ' '))
except Exception as e:
    print('EXC=' + str(e))
    traceback.print_exc()

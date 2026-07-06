#!/usr/bin/env python3
import json
import os
import secrets
import sqlite3
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get('XAPI_DATA_HOST', '127.0.0.1')
PORT = int(os.environ.get('XAPI_DATA_PORT', '19081'))
DB = os.environ.get('XAPI_DATA_MOCK_DB', '/opt/nw-api-phase0-preview/state/xapi_data_mock.db')
REQUEST_QUEUE_SIZE = int(os.environ.get('XAPI_DATA_MOCK_REQUEST_QUEUE_SIZE', '128'))


class TunedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = REQUEST_QUEUE_SIZE
DEFAULT_EMAIL = os.environ.get('XAPI_MOCK_ADMIN_EMAIL', 'root')
DEFAULT_PASSWORD = os.environ.get('XAPI_MOCK_ADMIN_PASS', 'password')


def js(obj):
    return json.dumps(obj, ensure_ascii=False).encode('utf-8')


def con():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = con()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE,
      username TEXT,
      password TEXT,
      role TEXT DEFAULT 'admin',
      status TEXT DEFAULT 'active',
      balance REAL DEFAULT 100,
      total_recharged REAL DEFAULT 100,
      created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS api_keys(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      name TEXT,
      key TEXT UNIQUE,
      status TEXT DEFAULT 'active',
      quota REAL DEFAULT 0,
      quota_used REAL DEFAULT 0,
      last_used_at INTEGER,
      created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS usage_logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      model TEXT,
      requested_model TEXT,
      input_tokens INTEGER DEFAULT 0,
      output_tokens INTEGER DEFAULT 0,
      cache_tokens INTEGER DEFAULT 0,
      total_cost REAL DEFAULT 0,
      created_at INTEGER
    );
    ''')
    user = c.execute('SELECT id FROM users WHERE email=?', (DEFAULT_EMAIL,)).fetchone()
    if not user:
        cur = c.execute('INSERT INTO users(email,username,password,role,status,balance,total_recharged,created_at) VALUES(?,?,?,?,?,?,?,?)',
                        (DEFAULT_EMAIL, 'root', DEFAULT_PASSWORD, 'admin', 'active', 100, 100, int(time.time())))
        uid = cur.lastrowid
    else:
        uid = user['id']
        c.execute('UPDATE users SET password=?, status="active", role="admin" WHERE id=?', (DEFAULT_PASSWORD, uid))
    key = c.execute('SELECT key FROM api_keys WHERE user_id=? AND status="active" ORDER BY id LIMIT 1', (uid,)).fetchone()
    if not key:
        c.execute('INSERT INTO api_keys(user_id,name,key,status,quota,quota_used,created_at) VALUES(?,?,?,?,?,?,?)',
                  (uid, 'phase0-preview-key', 'sk-phase0-preview-' + secrets.token_urlsafe(18).replace('-', '').replace('_', '')[:24], 'active', 0, 0, int(time.time())))
    c.commit(); c.close()


def row_to_list(row, fields):
    return [row[f] for f in fields]


class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def sendj(self, obj, code=200):
        b = js(obj)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        ln = int(self.headers.get('Content-Length', '0') or '0')
        return json.loads(self.rfile.read(ln) or b'{}')

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        uid = int(qs.get('uid', ['1'])[0] or 1)
        c = con()
        try:
            if path == '/xapi-data/health':
                return self.sendj({'ok': True, 'mode': 'phase0-mock'})
            if path in ('/xapi-data/dashboard', '/xapi-data/summary'):
                user = c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone() or c.execute('SELECT * FROM users ORDER BY id LIMIT 1').fetchone()
                stats = [str(c.execute('SELECT count(*) FROM usage_logs WHERE user_id=?', (uid,)).fetchone()[0]), '0', '0', '0', '0']
                keys = [[r['id'], r['name'], r['status'], r['key'][:6] + '****' + r['key'][-4:], r['quota'], r['quota_used'], ''] for r in c.execute('SELECT * FROM api_keys WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()]
                return self.sendj({'user': [user['id'], user['email'], user['username'], user['role'], user['status'], user['balance'], user['total_recharged']] if user else None,
                                   'stats': stats, 'today': ['0'] * 8, 'usage': [], 'keys': keys})
            if path == '/xapi-data/keys':
                keys = [[r['id'], r['name'], r['status'], r['key'][:6] + '****' + r['key'][-4:], r['quota'], r['quota_used'], ''] for r in c.execute('SELECT * FROM api_keys WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()]
                return self.sendj({'keys': keys})
            if path == '/xapi-data/usage':
                return self.sendj({'usage': []})
            if path == '/xapi-data/stats':
                return self.sendj({'total': ['0', '0', '0', '0'], 'daily': [], 'models': []})
            if path == '/xapi-data/models':
                return self.sendj({'models': [['gpt-5.5'], ['gpt-5.4'], ['gpt-5.4-mini'], ['gpt-image-2']]})
            if path == '/xapi-data/usage-ledger':
                return self.sendj({'source': 'phase0-mock', 'currency': 'backend_unit', 'ledger': []})
            if path == '/xapi-data/pricing':
                return self.sendj({'pricing': [
                    ['gpt-5.5', 'token', '0.00', '0.00', '0.00', '0.00'],
                    ['gpt-5.4', 'token', '0.00', '0.00', '0.00', '0.00'],
                    ['gpt-5.4-mini', 'token', '0.00', '0.00', '0.00', '0.00'],
                    ['gpt-image-2', 'token', '56.00', '0.00', '14.00', '210.00'],
                ]})
            return self.sendj({'error': 'not found'}, 404)
        finally:
            c.close()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        data = self.body()
        c = con()
        try:
            if path == '/xapi-data/users/auth':
                email = (data.get('email') or '').strip().lower()
                pw = data.get('password') or ''
                user = c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND password=? AND status="active"', (email, pw)).fetchone()
                if not user and email == 'root' and pw == DEFAULT_PASSWORD:
                    user = c.execute('SELECT * FROM users ORDER BY id LIMIT 1').fetchone()
                return self.sendj({'ok': bool(user), 'sub2_user_id': user['id'] if user else None, 'status': user['status'] if user else '', 'role': user['role'] if user else ''})
            if path == '/xapi-data/users':
                email = (data.get('email') or f'user{int(time.time())}@preview.local').strip().lower()
                username = (data.get('username') or email.split('@')[0])[:64]
                password = data.get('password') or secrets.token_urlsafe(12)
                c.execute('INSERT OR IGNORE INTO users(email,username,password,status,balance,total_recharged,created_at) VALUES(?,?,?,?,?,?,?)',
                          (email, username, password, 'active', 0, 0, int(time.time())))
                c.commit()
                uid = c.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()['id']
                return self.sendj({'sub2_user_id': uid, 'existed': False})
            if path == '/xapi-data/keys/verify':
                key = data.get('key') or ''
                r = c.execute('SELECT * FROM api_keys WHERE key=? AND status="active"', (key,)).fetchone()
                if not r:
                    return self.sendj({'ok': False, 'error': 'invalid key'}, 401)
                c.execute('UPDATE api_keys SET last_used_at=? WHERE id=?', (int(time.time()), r['id']))
                c.commit()
                return self.sendj({'ok': True, 'key_id': r['id'], 'user_id': r['user_id']})
            if path == '/xapi-data/keys':
                uid = int(data.get('uid') or 1)
                name = (data.get('name') or 'Preview Key')[:64]
                key = 'sk-preview-' + secrets.token_urlsafe(30).replace('-', '').replace('_', '')[:40]
                c.execute('INSERT INTO api_keys(user_id,name,key,status,quota,quota_used,created_at) VALUES(?,?,?,?,?,?,?)',
                          (uid, name, key, 'active', 0, 0, int(time.time())))
                c.commit()
                return self.sendj({'key': key})
            if path == '/xapi-data/keys/view':
                kid = int(data.get('id') or 0)
                r = c.execute('SELECT key FROM api_keys WHERE id=?', (kid,)).fetchone()
                return self.sendj({'ok': bool(r), 'key': r['key'] if r else ''}, 200 if r else 404)
            if path in ('/xapi-data/keys/rotate', '/xapi-data/keys/update', '/xapi-data/keys/disable', '/xapi-data/keys/delete', '/xapi-data/users/balance', '/xapi-data/users/update', '/xapi-data/users/delete', '/xapi-data/users/password'):
                return self.sendj({'ok': True, 'preview_mock': True})
            return self.sendj({'error': 'not found'}, 404)
        finally:
            c.close()


if __name__ == '__main__':
    init_db()
    TunedThreadingHTTPServer((HOST, PORT), H).serve_forever()

#!/usr/bin/env python3
'''Local regression tests for NW-API xapi-v1-wrapper.

Runs fully against mock xapi-data and mock upstream; no real key, no real Sub2API,
no production network required.
'''
import contextlib
import hashlib
import http.client
import importlib.util
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER_PATH = ROOT / 'services/xapi-v1-wrapper/xapi_v1_wrapper.py'


def load_wrapper():
    spec = importlib.util.spec_from_file_location('xapi_v1_wrapper_under_test', WRAPPER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ServerThread:
    def __init__(self, handler):
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)


class MockDataHandler(BaseHTTPRequestHandler):
    valid_key = 'sk-valid-test'
    disabled_key = 'sk-disabled-test'
    quota_key = 'sk-quota-test'

    def log_message(self, *args):
        return

    def do_POST(self):
        ln = int(self.headers.get('Content-Length', '0') or 0)
        data = json.loads(self.rfile.read(ln) or b'{}')
        if self.path == '/xapi-data/keys/verify' or self.path == '/keys/verify':
            key = data.get('key')
            if key == self.valid_key:
                return self.send_json({'ok': True, 'key_id': 11, 'user_id': 101})
            if key == self.disabled_key:
                return self.send_json({'ok': False, 'code': 'ACCOUNT_DISABLED', 'message': 'disabled'}, 403)
            if key == self.quota_key:
                return self.send_json({'ok': False, 'code': 'KEY_QUOTA_EXCEEDED', 'message': 'quota'}, 403)
            return self.send_json({'ok': False, 'code': 'INVALID_API_KEY', 'message': 'invalid'}, 401)
        return self.send_json({'error': 'not found'}, 404)

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MockUpstreamHandler(BaseHTTPRequestHandler):
    seen_request_ids = []

    def log_message(self, *args):
        return

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if self.path == '/v1/upstream-429':
            return self.send_json({'error': {'message': 'rate limit'}}, 429)
        return self.send_json({'ok': True, 'path': self.path})

    def do_POST(self):
        rid = self.headers.get('X-Request-Id') or self.headers.get('X-Request-ID')
        if rid:
            self.__class__.seen_request_ids.append(rid)
        ln = int(self.headers.get('Content-Length', '0') or 0)
        payload = json.loads(self.rfile.read(ln) or b'{}')
        if payload.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n')
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
            return
        return self.send_json({'id': 'chatcmpl-test', 'object': 'chat.completion', 'model': payload.get('model'), 'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}]})

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def request(base_url, method, path, body=None, key='sk-valid-test', headers=None, timeout=5):
    headers = dict(headers or {})
    if key is not None:
        headers.setdefault('Authorization', f'Bearer {key}')
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers.setdefault('Content-Type', 'application/json')
        headers.setdefault('Content-Length', str(len(data)))
    host, port = base_url.replace('http://', '').split(':')
    conn = http.client.HTTPConnection(host, int(port), timeout=timeout)
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    out_headers = dict(resp.getheaders())
    conn.close()
    return resp.status, out_headers, raw


class WrapperRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db_path = Path(cls.tmp.name) / 'portal.db'
        con = sqlite3.connect(db_path)
        con.executescript('''
CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT,status TEXT,sub2_user_id INTEGER);
CREATE TABLE user_models(user_id INTEGER,model TEXT,enabled INTEGER);
CREATE TABLE model_prices(model TEXT PRIMARY KEY,input_price REAL DEFAULT 0,output_price REAL DEFAULT 0,cache_price REAL DEFAULT 0,image_price REAL DEFAULT 0,note TEXT);
CREATE TABLE risk_rules(kind TEXT,pattern TEXT,action TEXT,status TEXT,id INTEGER PRIMARY KEY AUTOINCREMENT);
CREATE TABLE api_access_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,key_id INTEGER,ip TEXT,method TEXT,path TEXT,model TEXT,status INTEGER,error_code TEXT,latency_ms INTEGER,created_at INTEGER);
CREATE TABLE nw_api_keys(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,name TEXT NOT NULL,key_hash TEXT NOT NULL UNIQUE,key_prefix TEXT NOT NULL,key_suffix TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',quota REAL NOT NULL DEFAULT 0,quota_used REAL NOT NULL DEFAULT 0,last_used_at INTEGER,created_at INTEGER NOT NULL,rotated_at INTEGER,deleted_at INTEGER);
INSERT INTO users(id,email,status,sub2_user_id) VALUES(1,'u@example.com','active',101);
INSERT INTO user_models(user_id,model,enabled) VALUES(1,'gpt-5.5',1);
INSERT INTO model_prices(model) VALUES('gpt-5.5');
INSERT INTO model_prices(model) VALUES('gpt-5.4-mini');
''')
        nw_key = 'nwk_test_stage8_key_1234567890'
        con.execute('INSERT INTO nw_api_keys(id,user_id,name,key_hash,key_prefix,key_suffix,status,quota,quota_used,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(51,1,'stage8',hashlib.sha256(nw_key.encode()).hexdigest(),nw_key[:7],nw_key[-4:],'active',0,0,int(time.time())))
        con.commit(); con.close()
        cls.nw_key = nw_key
        cls.db_path = str(db_path)
        cls.data = ServerThread(MockDataHandler).start()
        cls.upstream = ServerThread(MockUpstreamHandler).start()
        cls.wrapper = load_wrapper()
        cls.wrapper.PORTAL_DB = cls.db_path
        cls.wrapper.DATA_BASE = cls.data.url + '/xapi-data'
        cls.wrapper.UPSTREAM = cls.upstream.url
        cls.wrapper.UPSTREAM_CONNECT_TIMEOUT = 2
        cls.wrapper.UPSTREAM_TIMEOUT = 5
        cls.wrapper.STREAM_IDLE_TIMEOUT = 2
        cls.wrapper_server = ServerThread(cls.wrapper.Handler).start()

    @classmethod
    def tearDownClass(cls):
        for s in [cls.wrapper_server, cls.upstream, cls.data]:
            with contextlib.suppress(Exception):
                s.stop()
        cls.tmp.cleanup()

    def test_models(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/models')
        self.assertEqual(status, 200, raw)
        self.assertIn('X-Request-Id', headers)
        data = json.loads(raw)
        ids = [m['id'] for m in data['data']]
        self.assertEqual(ids, ['gpt-5.5'])

    def test_models_with_nw_owned_key(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/models', key=self.nw_key)
        self.assertEqual(status, 200, raw)
        data = json.loads(raw)
        self.assertEqual([m['id'] for m in data['data']], ['gpt-5.5'])
        con = sqlite3.connect(self.db_path)
        row = con.execute('SELECT last_used_at FROM nw_api_keys WHERE id=51').fetchone()
        con.close()
        self.assertIsNotNone(row[0])

    def test_missing_key(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/models', key=None)
        self.assertEqual(status, 401)
        self.assertIn(b'INVALID_API_KEY', raw)

    def test_invalid_key(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/models', key='sk-bad')
        self.assertEqual(status, 401)
        self.assertIn(b'INVALID_API_KEY', raw)

    def test_model_not_allowed(self):
        status, headers, raw = request(self.wrapper_server.url, 'POST', '/v1/chat/completions', {'model': 'gpt-unknown', 'messages': []})
        self.assertEqual(status, 403)
        self.assertIn(b'MODEL_NOT_ALLOWED', raw)

    def test_non_stream_chat(self):
        rid = 'client-test-request-1'
        status, headers, raw = request(self.wrapper_server.url, 'POST', '/v1/chat/completions', {'model': 'gpt-5.5', 'messages': [{'role': 'user', 'content': 'hi'}]}, headers={'X-Request-Id': rid})
        self.assertEqual(status, 200, raw)
        self.assertEqual(headers.get('X-Request-Id'), rid)
        self.assertIn(rid, MockUpstreamHandler.seen_request_ids)
        self.assertEqual(json.loads(raw)['model'], 'gpt-5.5')

    def test_stream_chat(self):
        status, headers, raw = request(self.wrapper_server.url, 'POST', '/v1/chat/completions', {'model': 'gpt-5.5', 'messages': [], 'stream': True})
        self.assertEqual(status, 200, raw)
        self.assertIn(b'data: [DONE]', raw)

    def test_upstream_429_passthrough(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/upstream-429')
        self.assertEqual(status, 429)
        self.assertIn(b'rate limit', raw)

    def test_head(self):
        status, headers, raw = request(self.wrapper_server.url, 'HEAD', '/v1/head')
        self.assertEqual(status, 200)
        self.assertEqual(raw, b'')

    def test_head_models_local(self):
        status, headers, raw = request(self.wrapper_server.url, 'HEAD', '/v1/models')
        self.assertEqual(status, 200)
        self.assertEqual(raw, b'')
        self.assertIn('Content-Length', headers)

    def test_options(self):
        status, headers, raw = request(self.wrapper_server.url, 'OPTIONS', '/v1/chat/completions', key=None)
        self.assertEqual(status, 204)

    def test_access_log_written(self):
        status, headers, raw = request(self.wrapper_server.url, 'GET', '/v1/models')
        self.assertEqual(status, 200, raw)
        # Direct log_access verification catches schema drift without depending on
        # other tests' ordering or swallowed production logging exceptions.
        self.wrapper.log_access(user_id=1, key_id=11, ip='127.0.0.1', method='GET', path='/v1/models', status=200, latency_ms=1, request_id='req_manual_test')
        con = sqlite3.connect(self.db_path)
        n = con.execute('SELECT count(*) FROM api_access_logs').fetchone()[0]
        rid = con.execute("SELECT request_id FROM api_access_logs WHERE request_id='req_manual_test'").fetchone()
        con.close()
        self.assertGreater(n, 0)
        self.assertEqual(rid[0], 'req_manual_test')

    def test_ip_blocked_access_log(self):
        con = sqlite3.connect(self.db_path)
        con.execute(
            'INSERT INTO risk_rules(kind,pattern,action,status) VALUES(?,?,?,?)',
            ('ip', '1.2.3.4', 'block', 'active'),
        )
        con.commit(); con.close()
        try:
            status, headers, raw = request(
                self.wrapper_server.url,
                'GET',
                '/v1/models',
                headers={'X-Forwarded-For': '1.2.3.4', 'X-Request-Id': 'req_ip_block_test'},
            )
            self.assertEqual(status, 403, raw)
            self.assertIn(b'IP_BLOCKED', raw)
            con = sqlite3.connect(self.db_path)
            row = con.execute(
                "SELECT user_id,key_id,ip,status,error_code,request_id FROM api_access_logs WHERE request_id='req_ip_block_test' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            self.assertIsNotNone(row)
            self.assertIsNone(row[0])
            self.assertIsNone(row[1])
            self.assertEqual(row[2], '1.2.3.4')
            self.assertEqual(row[3], 403)
            self.assertEqual(row[4], 'IP_BLOCKED')
            self.assertEqual(row[5], 'req_ip_block_test')
        finally:
            con = sqlite3.connect(self.db_path)
            con.execute("DELETE FROM risk_rules WHERE pattern='1.2.3.4' AND action='block'")
            con.commit(); con.close()

    def test_ip_blocked_post_body_access_log(self):
        con = sqlite3.connect(self.db_path)
        con.execute(
            'INSERT INTO risk_rules(kind,pattern,action,status) VALUES(?,?,?,?)',
            ('ip', '5.6.7.8', 'block', 'active'),
        )
        con.commit(); con.close()
        try:
            status, headers, raw = request(
                self.wrapper_server.url,
                'POST',
                '/v1/chat/completions',
                {'model': 'gpt-5.5', 'messages': [{'role': 'user', 'content': 'blocked'}]},
                headers={'X-Forwarded-For': '5.6.7.8', 'X-Request-Id': 'req_ip_block_post_test'},
            )
            self.assertEqual(status, 403, raw)
            self.assertIn(b'IP_BLOCKED', raw)
            con = sqlite3.connect(self.db_path)
            row = con.execute(
                "SELECT user_id,key_id,ip,method,path,model,status,error_code,request_id FROM api_access_logs WHERE request_id='req_ip_block_post_test' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            self.assertIsNotNone(row)
            self.assertIsNone(row[0])
            self.assertIsNone(row[1])
            self.assertEqual(row[2], '5.6.7.8')
            self.assertEqual(row[3], 'POST')
            self.assertEqual(row[4], '/v1/chat/completions')
            self.assertEqual(row[5] or '', '')
            self.assertEqual(row[6], 403)
            self.assertEqual(row[7], 'IP_BLOCKED')
            self.assertEqual(row[8], 'req_ip_block_post_test')
        finally:
            con = sqlite3.connect(self.db_path)
            con.execute("DELETE FROM risk_rules WHERE pattern='5.6.7.8' AND action='block'")
            con.commit(); con.close()

    def test_auth_reject_access_log(self):
        status, headers, raw = request(
            self.wrapper_server.url,
            'GET',
            '/v1/models',
            key='sk-bad',
            headers={'X-Request-Id': 'req_auth_reject_test'},
        )
        self.assertEqual(status, 401, raw)
        self.assertIn(b'INVALID_API_KEY', raw)
        con = sqlite3.connect(self.db_path)
        row = con.execute(
            "SELECT user_id,key_id,ip,status,error_code,request_id FROM api_access_logs WHERE request_id='req_auth_reject_test' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        self.assertIsNotNone(row)
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertEqual(row[2], '127.0.0.1')
        self.assertEqual(row[3], 401)
        self.assertEqual(row[4], 'INVALID_API_KEY')
        self.assertEqual(row[5], 'req_auth_reject_test')

    def test_model_not_allowed_access_log(self):
        status, headers, raw = request(
            self.wrapper_server.url,
            'POST',
            '/v1/chat/completions',
            {'model': 'gpt-unknown', 'messages': []},
            headers={'X-Request-Id': 'req_model_reject_test'},
        )
        self.assertEqual(status, 403, raw)
        self.assertIn(b'MODEL_NOT_ALLOWED', raw)
        con = sqlite3.connect(self.db_path)
        row = con.execute(
            "SELECT user_id,key_id,ip,method,path,model,status,error_code,request_id FROM api_access_logs WHERE request_id='req_model_reject_test' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 11)
        self.assertEqual(row[2], '127.0.0.1')
        self.assertEqual(row[3], 'POST')
        self.assertEqual(row[4], '/v1/chat/completions')
        self.assertEqual(row[5], 'gpt-unknown')
        self.assertEqual(row[6], 403)
        self.assertEqual(row[7], 'MODEL_NOT_ALLOWED')
        self.assertEqual(row[8], 'req_model_reject_test')


if __name__ == '__main__':
    unittest.main(verbosity=2)

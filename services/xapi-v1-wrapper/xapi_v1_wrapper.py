#!/usr/bin/env python3
"""NW-API OpenAI-compatible /v1 wrapper.

This process sits in front of the internal Sub2API tunnel. It enforces portal
API-key, account, IP, and model policy while preserving OpenAI-compatible
streaming responses.
"""
import json
import os
import ipaddress
import select
import socket
import sqlite3
import time
import secrets
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

HOST = os.environ.get('XAPI_WRAPPER_HOST', '127.0.0.1')
PORT = int(os.environ.get('XAPI_WRAPPER_PORT', '18182'))
PORTAL_DB = os.environ.get('XAPI_PORTAL_DB', '/opt/xapi-portal/xapi_portal.db')
UPSTREAM = os.environ.get('XAPI_UPSTREAM', 'http://127.0.0.1:18066').rstrip('/')
DATA_BASE = os.environ.get('XAPI_DATA_BASE', UPSTREAM + '/xapi-data').rstrip('/')

DATA_TIMEOUT = float(os.environ.get('XAPI_DATA_TIMEOUT_SECONDS', '25'))
UPSTREAM_TIMEOUT = float(os.environ.get('XAPI_UPSTREAM_TIMEOUT_SECONDS', '540'))
UPSTREAM_CONNECT_TIMEOUT = float(os.environ.get('XAPI_UPSTREAM_CONNECT_TIMEOUT_SECONDS', '10'))
STREAM_IDLE_TIMEOUT = float(os.environ.get('XAPI_STREAM_IDLE_TIMEOUT_SECONDS', '180'))
STREAM_CHUNK_SIZE = int(os.environ.get('XAPI_STREAM_CHUNK_SIZE', '8192'))

HOP_BY_HOP_HEADERS = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length',
    'content-encoding',
}

REQUEST_ID_HEADER = 'X-Request-Id'
REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,80}$')
_REQUEST_CONTEXT = threading.local()


def make_request_id(handler=None):
    if handler is not None:
        incoming = (handler.headers.get(REQUEST_ID_HEADER) or handler.headers.get('X-Request-ID') or '').strip()
        if incoming and REQUEST_ID_RE.fullmatch(incoming):
            return incoming[:80]
    return 'req_' + secrets.token_hex(12)


def current_request_id():
    return getattr(_REQUEST_CONTEXT, 'request_id', '')


def json_error(handler, code, message, status=403):
    body = json.dumps({'code': code, 'message': message}, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Connection', 'close')
    handler.end_headers()
    handler.wfile.write(body)
    handler.wfile.flush()


def post_json(path, payload):
    req = urllib.request.Request(
        DATA_BASE + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=DATA_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def allowed_models(portal_user_id):
    con = sqlite3.connect(PORTAL_DB)
    try:
        rows = con.execute(
            'SELECT model FROM user_models WHERE user_id=? AND enabled=1',
            (portal_user_id,),
        ).fetchall()
        if not rows:
            rows = con.execute('SELECT model FROM model_prices ORDER BY model').fetchall()
        return {row[0] for row in rows}
    finally:
        con.close()


def portal_user_by_sub2(sub2_user_id):
    con = sqlite3.connect(PORTAL_DB)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(
            'SELECT * FROM users WHERE sub2_user_id=? AND status="active"',
            (sub2_user_id,),
        ).fetchone()
    finally:
        con.close()


def client_ip(handler):
    xff = handler.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    return xff or handler.client_address[0]


def risk_allowed(ip):
    con = sqlite3.connect(PORTAL_DB)
    try:
        rows = con.execute(
            'SELECT pattern,action FROM risk_rules '
            'WHERE kind="ip" AND status="active" '
            'ORDER BY CASE action WHEN "allow" THEN 0 ELSE 1 END,id DESC'
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return True, ''
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return True, ''
    matched_allow = False
    for pattern, action in rows:
        try:
            ok = (addr in ipaddress.ip_network(pattern, strict=False)) if '/' in pattern else (addr == ipaddress.ip_address(pattern))
        except Exception:
            ok = False
        if ok and action == 'allow':
            matched_allow = True
        if ok and action == 'block' and not matched_allow:
            return False, pattern
    return True, ''


def log_access(user_id=None, key_id=None, ip='', method='', path='', model='', status=0, error_code='', latency_ms=0, request_id=''):
    con = None
    try:
        con = sqlite3.connect(PORTAL_DB)
        con.execute(
            'CREATE TABLE IF NOT EXISTS api_access_logs('
            'id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,key_id INTEGER,'
            'ip TEXT,method TEXT,path TEXT,model TEXT,status INTEGER,'
            'error_code TEXT,latency_ms INTEGER,created_at INTEGER)'
        )
        try:
            con.execute('ALTER TABLE api_access_logs ADD COLUMN request_id TEXT')
        except sqlite3.OperationalError as exc:
            if 'duplicate column' not in str(exc).lower():
                raise
        con.execute('CREATE INDEX IF NOT EXISTS idx_api_access_logs_request_id ON api_access_logs(request_id)')
        con.execute('DELETE FROM api_access_logs WHERE created_at < ?', (int(time.time()) - 90 * 86400,))
        rid = request_id or current_request_id()
        con.execute(
            'INSERT INTO api_access_logs(user_id,key_id,ip,method,path,model,status,error_code,latency_ms,created_at,request_id) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (user_id, key_id, ip, method, path, model, status, error_code, latency_ms, int(time.time()), rid),
        )
        con.commit()
    except Exception:
        pass
    finally:
        if con is not None:
            con.close()


def upstream_reachable(url):
    parts = urlsplit(url)
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    if not host:
        return False, 'missing upstream host'
    try:
        with socket.create_connection((host, port), timeout=UPSTREAM_CONNECT_TIMEOUT):
            return True, ''
    except OSError as exc:
        return False, str(exc)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        # Keep stdlib access noise low; structured access is stored in SQLite.
        return

    def end_headers(self):
        rid = getattr(self, 'request_id', '')
        if rid:
            self.send_header(REQUEST_ID_HEADER, rid)
        super().end_headers()

    def do_GET(self):
        self.proxy()

    def do_HEAD(self):
        self.proxy()

    def do_POST(self):
        self.proxy()

    def do_OPTIONS(self):
        self.request_id = make_request_id(self)
        _REQUEST_CONTEXT.request_id = self.request_id
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'authorization,content-type')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def proxy(self):
        self.request_id = make_request_id(self)
        _REQUEST_CONTEXT.request_id = self.request_id
        started = time.time()
        model = ''
        portal_user = None
        key_id = None
        cip = client_ip(self)

        ok, rule = risk_allowed(cip)
        if not ok:
            log_access(ip=cip, method=self.command, path=self.path, status=403, error_code='IP_BLOCKED', latency_ms=self.elapsed(started))
            return json_error(self, 'IP_BLOCKED', f'Client IP blocked: {rule}', 403)

        auth = self.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            log_access(ip=cip, method=self.command, path=self.path, status=401, error_code='INVALID_API_KEY', latency_ms=self.elapsed(started))
            return json_error(self, 'INVALID_API_KEY', 'Missing API key', 401)
        api_key = auth.split(None, 1)[1].strip()

        try:
            info = post_json('/keys/verify', {'key': api_key})
        except Exception:
            log_access(ip=cip, method=self.command, path=self.path, status=401, error_code='INVALID_API_KEY', latency_ms=self.elapsed(started))
            return json_error(self, 'INVALID_API_KEY', 'Invalid API key', 401)
        if not info.get('ok'):
            code = info.get('code', 'INVALID_API_KEY')
            log_access(ip=cip, method=self.command, path=self.path, status=401, error_code=code, latency_ms=self.elapsed(started))
            return json_error(self, code, info.get('message', 'Invalid API key'), 401)

        sub2_uid = int(info['user_id'])
        key_id = int(info['key_id'])
        portal_user = portal_user_by_sub2(sub2_uid)
        if not portal_user:
            log_access(user_id=sub2_uid, key_id=key_id, ip=cip, method=self.command, path=self.path, status=403, error_code='ACCOUNT_DISABLED', latency_ms=self.elapsed(started))
            return json_error(self, 'ACCOUNT_DISABLED', 'Account disabled', 403)

        if self.command == 'GET' and self.path.split('?', 1)[0].rstrip('/') == '/v1/models':
            return self.respond_models(portal_user, key_id, cip, started)

        body = self.read_body()
        if body and self.headers.get('Content-Type', '').split(';')[0].lower() == 'application/json':
            try:
                data = json.loads(body.decode('utf-8') or '{}')
                model = data.get('model') or ''
                if model and model not in allowed_models(portal_user['id']):
                    log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=403, error_code='MODEL_NOT_ALLOWED', latency_ms=self.elapsed(started))
                    return json_error(self, 'MODEL_NOT_ALLOWED', f'Model not allowed: {model}', 403)
            except json.JSONDecodeError:
                pass

        upstream_url = UPSTREAM + self.path
        reachable, reason = upstream_reachable(UPSTREAM)
        if not reachable:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=502, error_code='UPSTREAM_TUNNEL_DOWN', latency_ms=self.elapsed(started))
            return json_error(self, 'UPSTREAM_TUNNEL_DOWN', f'Upstream tunnel unavailable: {reason}', 502)

        try:
            self.forward_to_upstream(upstream_url, body, portal_user, key_id, cip, model, started)
        except socket.timeout:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=504, error_code='UPSTREAM_TIMEOUT', latency_ms=self.elapsed(started))
            return json_error(self, 'UPSTREAM_TIMEOUT', 'Upstream timed out', 504)
        except BrokenPipeError:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=499, error_code='CLIENT_CLOSED', latency_ms=self.elapsed(started))
        except Exception as exc:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=502, error_code='UPSTREAM_ERROR', latency_ms=self.elapsed(started))
            return json_error(self, 'UPSTREAM_ERROR', str(exc), 502)

    def read_body(self):
        length = int(self.headers.get('Content-Length', '0') or 0)
        return self.rfile.read(length) if length else b''

    def respond_models(self, portal_user, key_id, cip, started):
        models = sorted(allowed_models(portal_user['id']))
        payload = {'object': 'list', 'data': [{'id': m, 'object': 'model', 'created': 0, 'owned_by': 'nw-api'} for m in models]}
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, status=200, latency_ms=self.elapsed(started))

    def forward_to_upstream(self, upstream_url, body, portal_user, key_id, cip, model, started):
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in ('host', 'content-length', 'connection', 'accept-encoding')
        }
        headers[REQUEST_ID_HEADER] = getattr(self, 'request_id', '') or current_request_id()
        request = urllib.request.Request(
            upstream_url,
            data=(body if self.command not in ('GET', 'HEAD') else None),
            headers=headers,
            method=self.command,
        )
        try:
            response = urllib.request.urlopen(request, timeout=UPSTREAM_CONNECT_TIMEOUT)
        except urllib.error.HTTPError as exc:
            return self.forward_http_error(exc, portal_user, key_id, cip, model, started)
        with response:
            self.send_response(response.status)
            content_length = None
            for key, value in response.headers.items():
                lower = key.lower()
                if lower == 'content-length':
                    try:
                        content_length = int(value)
                    except ValueError:
                        content_length = None
                    self.send_header(key, value)
                elif lower not in HOP_BY_HOP_HEADERS:
                    self.send_header(key, value)
            chunked_downstream = content_length is None and self.command != 'HEAD'
            if chunked_downstream:
                self.send_header('Transfer-Encoding', 'chunked')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            try:
                if self.command != 'HEAD':
                    self.stream_response(response, chunked_downstream, content_length)
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=response.status, latency_ms=self.elapsed(started))
            except socket.timeout:
                self.close_connection = True
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=504, error_code='UPSTREAM_STREAM_TIMEOUT', latency_ms=self.elapsed(started))
            except BrokenPipeError:
                self.close_connection = True
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=499, error_code='CLIENT_CLOSED', latency_ms=self.elapsed(started))

    def stream_response(self, response, chunked_downstream, content_length=None):
        sock = response.fp.raw._sock  # stdlib HTTPResponse socket; used for idle timeout between chunks.
        sock.settimeout(STREAM_IDLE_TIMEOUT)
        deadline = time.monotonic() + UPSTREAM_TIMEOUT
        remaining_body = content_length
        while True:
            if remaining_body is not None and remaining_body <= 0:
                break
            remaining_total = deadline - time.monotonic()
            if remaining_total <= 0:
                raise socket.timeout('upstream total timeout')
            wait = min(STREAM_IDLE_TIMEOUT, remaining_total)
            ready, _, _ = select.select([sock], [], [], wait)
            if not ready:
                raise socket.timeout('upstream stream idle timeout')
            read_size = STREAM_CHUNK_SIZE if remaining_body is None else min(STREAM_CHUNK_SIZE, remaining_body)
            chunk = response.read(read_size)
            if not chunk:
                break
            if remaining_body is not None:
                remaining_body -= len(chunk)
            if chunked_downstream:
                self.wfile.write((f'{len(chunk):X}\r\n').encode('ascii'))
                self.wfile.write(chunk)
                self.wfile.write(b'\r\n')
            else:
                self.wfile.write(chunk)
            self.wfile.flush()
        if chunked_downstream:
            self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush()

    def forward_http_error(self, exc, portal_user, key_id, cip, model, started):
        payload = exc.read()
        status = exc.code
        error_code = 'UPSTREAM_HTTP_ERROR'
        if status == 429:
            error_code = 'UPSTREAM_RATE_LIMIT'
        elif status in (502, 503, 504):
            error_code = 'UPSTREAM_UNAVAILABLE'
        self.send_response(status)
        for key, value in exc.headers.items():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(key, value)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()
        log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=status, error_code=error_code, latency_ms=self.elapsed(started))

    @staticmethod
    def elapsed(started):
        return int((time.time() - started) * 1000)


if __name__ == '__main__':
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

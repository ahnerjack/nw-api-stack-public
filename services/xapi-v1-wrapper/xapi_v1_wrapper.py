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
import threading
import sys
from pathlib import Path
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gateway_core import (
    AuthPolicy, IPRiskPolicy, ModelAllowPolicy, PolicyPipeline,
    REQUEST_ID_HEADER, build_access_log_record, build_model_list_payload, encode_chunk,
    make_request_id_from_headers, normalize_request, proxy_request_headers,
    should_chunk_downstream, should_forward_response_header, upstream_http_error_code,
)

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

_REQUEST_CONTEXT = threading.local()


def make_request_id(handler=None):
    return make_request_id_from_headers(handler.headers if handler is not None else {})


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
    record = build_access_log_record(
        user_id=user_id, key_id=key_id, ip=ip, method=method, path=path,
        model=model, status=status, error_code=error_code,
        latency_ms=latency_ms, request_id=request_id or current_request_id(),
    )
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
        con.execute(
            'INSERT INTO api_access_logs(user_id,key_id,ip,method,path,model,status,error_code,latency_ms,created_at,request_id) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            record.insert_values(int(time.time())),
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

        req = normalize_request(
            method=self.command,
            path=self.path,
            headers=self.headers,
            body=b'',
            fallback_ip=self.client_address[0],
        )
        cip = req.client_ip
        self.request_id = req.request_id
        _REQUEST_CONTEXT.request_id = self.request_id

        policy_result = PolicyPipeline([
            IPRiskPolicy(risk_allowed),
            AuthPolicy(lambda key: post_json('/keys/verify', {'key': key}), portal_user_by_sub2),
        ]).run(req)
        if not policy_result.allowed:
            log_access(user_id=policy_result.context.get('sub2_uid'), key_id=policy_result.context.get('key_id'), ip=cip, method=self.command, path=self.path, status=policy_result.http_status, error_code=policy_result.error_code, latency_ms=self.elapsed(started), request_id=self.request_id)
            return json_error(self, policy_result.error_code, policy_result.error_message, policy_result.http_status)

        sub2_uid = int(policy_result.context['sub2_uid'])
        key_id = int(policy_result.context['key_id'])
        portal_user = policy_result.context['portal_user']

        if self.command == 'GET' and self.path.split('?', 1)[0].rstrip('/') == '/v1/models':
            return self.respond_models(portal_user, key_id, cip, started)

        body = self.read_body()
        model_req = normalize_request(self.command, self.path, self.headers, body, self.client_address[0])
        model = model_req.model
        if model:
            model_result = PolicyPipeline([ModelAllowPolicy(allowed_models)]).run(model_req, {'portal_user': portal_user})
            if not model_result.allowed:
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=model_result.http_status, error_code=model_result.error_code, latency_ms=self.elapsed(started), request_id=self.request_id)
                return json_error(self, model_result.error_code, model_result.error_message, model_result.http_status)

        upstream_url = UPSTREAM + self.path
        reachable, reason = upstream_reachable(UPSTREAM)
        if not reachable:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=502, error_code='UPSTREAM_TUNNEL_DOWN', latency_ms=self.elapsed(started), request_id=self.request_id)
            return json_error(self, 'UPSTREAM_TUNNEL_DOWN', f'Upstream tunnel unavailable: {reason}', 502)

        try:
            self.forward_to_upstream(upstream_url, body, portal_user, key_id, cip, model, started)
        except socket.timeout:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=504, error_code='UPSTREAM_TIMEOUT', latency_ms=self.elapsed(started), request_id=self.request_id)
            return json_error(self, 'UPSTREAM_TIMEOUT', 'Upstream timed out', 504)
        except BrokenPipeError:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=499, error_code='CLIENT_CLOSED', latency_ms=self.elapsed(started), request_id=self.request_id)
        except Exception as exc:
            log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=502, error_code='UPSTREAM_ERROR', latency_ms=self.elapsed(started), request_id=self.request_id)
            return json_error(self, 'UPSTREAM_ERROR', str(exc), 502)

    def read_body(self):
        length = int(self.headers.get('Content-Length', '0') or 0)
        return self.rfile.read(length) if length else b''

    def respond_models(self, portal_user, key_id, cip, started):
        models = allowed_models(portal_user['id'])
        body = build_model_list_payload(models)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, status=200, latency_ms=self.elapsed(started), request_id=self.request_id)

    def forward_to_upstream(self, upstream_url, body, portal_user, key_id, cip, model, started):
        headers = proxy_request_headers(dict(self.headers.items()), getattr(self, 'request_id', '') or current_request_id())
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
                elif should_forward_response_header(key):
                    self.send_header(key, value)
            chunked_downstream = should_chunk_downstream(content_length, self.command)
            if chunked_downstream:
                self.send_header('Transfer-Encoding', 'chunked')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            try:
                if self.command != 'HEAD':
                    self.stream_response(response, chunked_downstream, content_length)
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=response.status, latency_ms=self.elapsed(started), request_id=self.request_id)
            except socket.timeout:
                self.close_connection = True
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=504, error_code='UPSTREAM_STREAM_TIMEOUT', latency_ms=self.elapsed(started), request_id=self.request_id)
            except BrokenPipeError:
                self.close_connection = True
                log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=499, error_code='CLIENT_CLOSED', latency_ms=self.elapsed(started), request_id=self.request_id)

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
                self.wfile.write(encode_chunk(chunk))
            else:
                self.wfile.write(chunk)
            self.wfile.flush()
        if chunked_downstream:
            self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush()

    def forward_http_error(self, exc, portal_user, key_id, cip, model, started):
        payload = exc.read()
        status = exc.code
        error_code = upstream_http_error_code(status)
        self.send_response(status)
        for key, value in exc.headers.items():
            if should_forward_response_header(key):
                self.send_header(key, value)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()
        log_access(user_id=portal_user['id'], key_id=key_id, ip=cip, method=self.command, path=self.path, model=model, status=status, error_code=error_code, latency_ms=self.elapsed(started), request_id=self.request_id)

    @staticmethod
    def elapsed(started):
        return int((time.time() - started) * 1000)


if __name__ == '__main__':
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

#!/usr/bin/env python3
import http.client
import html
import os
import socketserver
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PREVIEW_PORT = int(os.environ.get('NW_API_PREVIEW_PORT', '9088'))
PREVIEW_HOST = os.environ.get('NW_API_PREVIEW_HOST', '0.0.0.0')
PORTAL_BASE = os.environ.get('NW_API_PREVIEW_PORTAL_BASE', 'http://127.0.0.1:19080').rstrip('/')
WRAPPER_BASE = os.environ.get('NW_API_PREVIEW_WRAPPER_BASE', 'http://127.0.0.1:19082').rstrip('/')
BRAND = os.environ.get('NW_API_PREVIEW_BRAND', 'NW-API 阶段0预览')
REQUEST_QUEUE_SIZE = int(os.environ.get('NW_API_PREVIEW_REQUEST_QUEUE_SIZE', '128'))
PROXY_TIMEOUT = float(os.environ.get('NW_API_PREVIEW_PROXY_TIMEOUT_SECONDS', '180'))
STREAM_CHUNK_SIZE = int(os.environ.get('NW_API_PREVIEW_STREAM_CHUNK_SIZE', '8192'))


class TunedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = REQUEST_QUEUE_SIZE


def upstream_for(path):
    if path == '/v1' or path.startswith('/v1/'):
        return WRAPPER_BASE, path
    if path == '/nv-api':
        return PORTAL_BASE, '/'
    if path.startswith('/nv-api/'):
        return PORTAL_BASE, path[len('/nv-api'):]
    return None, None


def rewrite_body(data, content_type):
    if not data or b'text/html' not in content_type.lower().encode('latin1', 'ignore'):
        return data
    text = data.decode('utf-8', 'replace')
    replacements = {
        'href="/': 'href="/nv-api/',
        "href='/": "href='/nv-api/",
        'action="/': 'action="/nv-api/',
        "action='/": "action='/nv-api/",
        'src="/': 'src="/nv-api/',
        "src='/": "src='/nv-api/",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?'):
            return self.home()
        return self.proxy()

    def do_HEAD(self):
        return self.proxy(head_only=True)

    def do_POST(self):
        return self.proxy()

    def do_PUT(self):
        return self.proxy()

    def do_DELETE(self):
        return self.proxy()

    def do_OPTIONS(self):
        return self.proxy()

    def home(self):
        body = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(BRAND)}</title>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f172a;color:#e5e7eb}}
.wrap{{max-width:880px;margin:8vh auto;padding:32px}}
.card{{background:rgba(15,23,42,.88);border:1px solid rgba(148,163,184,.25);border-radius:24px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.35)}}
h1{{font-size:30px;margin:0 0 10px}}p{{color:#94a3b8;line-height:1.7}}a.btn{{display:inline-block;margin:10px 12px 0 0;padding:12px 18px;border-radius:14px;background:#2563eb;color:white;text-decoration:none}}code{{background:#111827;padding:2px 6px;border-radius:6px}}
</style></head><body><div class="wrap"><div class="card">
<h1>{html.escape(BRAND)}</h1>
<p>真实预览环境，端口 <code>{PREVIEW_PORT}</code>。不影响正式站。</p>
<a class="btn" href="/nv-api/">打开后台预览</a>
<a class="btn" href="/v1/models">测试 /v1/models</a>
<p>Portal: <code>{html.escape(PORTAL_BASE)}</code><br>Wrapper: <code>{html.escape(WRAPPER_BASE)}</code></p>
</div></div></body></html>'''.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def proxy(self, head_only=False):
        parsed = urllib.parse.urlsplit(self.path)
        base, upstream_path = upstream_for(parsed.path)
        if not base:
            body = b'not found\n'
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return
        target = urllib.parse.urlsplit(base)
        assert upstream_path is not None
        assert target.hostname is not None
        path = upstream_path + (('?' + parsed.query) if parsed.query else '')
        body_len = int(self.headers.get('Content-Length', '0') or '0')
        body = self.rfile.read(body_len) if body_len else None
        conn = http.client.HTTPConnection(target.hostname, target.port or 80, timeout=PROXY_TIMEOUT)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'connection', 'content-length')}
        headers['Host'] = target.netloc
        if body is not None:
            headers['Content-Length'] = str(len(body))
        try:
            conn.request(self.command, path, body=body, headers=headers)
            resp = conn.getresponse()
            if base == WRAPPER_BASE:
                return self.stream_proxy_response(resp, head_only)
            data = b'' if head_only else resp.read()
            content_type = resp.getheader('Content-Type', '')
            if base == PORTAL_BASE and not head_only:
                data = rewrite_body(data, content_type)
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                lk = k.lower()
                if lk in ('connection', 'content-length', 'transfer-encoding', 'content-encoding'):
                    continue
                if lk == 'location' and v.startswith('/') and base == PORTAL_BASE:
                    v = '/nv-api' + v
                if lk == 'set-cookie' and 'Path=/' in v and base == PORTAL_BASE:
                    v = v.replace('Path=/', 'Path=/nv-api/')
                self.send_header(k, v)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
        except Exception as exc:
            data = f'preview proxy error: {exc}\n'.encode()
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
        finally:
            conn.close()

    def stream_proxy_response(self, resp, head_only=False):
        self.send_response(resp.status, resp.reason)
        content_length = resp.getheader('Content-Length')
        chunked_upstream = 'chunked' in (resp.getheader('Transfer-Encoding') or '').lower()
        for k, v in resp.getheaders():
            lk = k.lower()
            if lk in ('connection', 'transfer-encoding', 'content-encoding'):
                continue
            if lk == 'content-length' and chunked_upstream:
                continue
            self.send_header(k, v)
        if not content_length and not head_only:
            self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        if head_only:
            return
        try:
            while True:
                if hasattr(resp, 'read1'):
                    chunk = resp.read1(STREAM_CHUNK_SIZE)
                else:
                    chunk = resp.read(1)
                if not chunk:
                    break
                if content_length:
                    self.wfile.write(chunk)
                else:
                    self.wfile.write(f'{len(chunk):X}\r\n'.encode('ascii'))
                    self.wfile.write(chunk)
                    self.wfile.write(b'\r\n')
                self.wfile.flush()
            if not content_length:
                self.wfile.write(b'0\r\n\r\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            self.close_connection = True

if __name__ == '__main__':
    TunedThreadingHTTPServer((PREVIEW_HOST, PREVIEW_PORT), Handler).serve_forever()

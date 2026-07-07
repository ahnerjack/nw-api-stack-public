#!/usr/bin/env python3
"""Pure Gateway Core helpers for the NW-API /v1 wrapper.

This module intentionally avoids network, filesystem, sqlite, and BaseHTTPRequestHandler
side effects. HTTP adapters such as xapi_v1_wrapper.py pass primitive data in and render
responses outside the core.
"""
from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from typing import Callable, Mapping, Any, Protocol

REQUEST_ID_HEADER = 'X-Request-Id'
REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9_.:-]{1,80}$')

HOP_BY_HOP_HEADERS = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length',
    'content-encoding',
}


@dataclass(frozen=True)
class ErrorResponse:
    code: str
    message: str
    status: int = 403

    def body(self) -> bytes:
        return json.dumps({'code': self.code, 'message': self.message}, ensure_ascii=False).encode('utf-8')


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    error_code: str = ''
    error_message: str = ''
    http_status: int = 200
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, **context):
        return cls(True, context=context)

    @classmethod
    def deny(cls, code: str, message: str, status: int, **context):
        return cls(False, code, message, status, context)


class IPRiskPolicy:
    def __init__(self, checker: Callable[[str], tuple[bool, str]]):
        self.checker = checker

    def evaluate(self, req: 'NormalizedRequest', ctx: dict[str, Any] | None = None) -> PolicyResult:
        ok, rule = self.checker(req.client_ip)
        if not ok:
            return PolicyResult.deny('IP_BLOCKED', f'Client IP blocked: {rule}', 403, rule=rule)
        return PolicyResult.allow()


class AuthPolicy:
    def __init__(self, key_verifier: Callable[[str], Mapping[str, Any]], portal_user_loader: Callable[[Mapping[str, Any]], Any]):
        self.key_verifier = key_verifier
        self.portal_user_loader = portal_user_loader

    def evaluate(self, req: 'NormalizedRequest', ctx: dict[str, Any] | None = None) -> PolicyResult:
        if not req.api_key:
            return PolicyResult.deny('INVALID_API_KEY', 'Missing API key', 401)
        try:
            info = self.key_verifier(req.api_key)
        except Exception:
            return PolicyResult.deny('INVALID_API_KEY', 'Invalid API key', 401)
        if not info.get('ok'):
            code = str(info.get('code') or 'INVALID_API_KEY')
            return PolicyResult.deny(code, str(info.get('message') or 'Invalid API key'), 401)
        sub2_uid = int(info['user_id'])
        key_id = int(info['key_id'])
        portal_user = self.portal_user_loader(info)
        if not portal_user:
            return PolicyResult.deny('ACCOUNT_DISABLED', 'Account disabled', 403, sub2_uid=sub2_uid, key_id=key_id)
        return PolicyResult.allow(sub2_uid=sub2_uid, key_id=key_id, portal_user=portal_user)


class ModelAllowPolicy:
    def __init__(self, allowed_models_loader: Callable[[int], set[str]]):
        self.allowed_models_loader = allowed_models_loader

    def evaluate(self, req: 'NormalizedRequest', ctx: dict[str, Any] | None = None) -> PolicyResult:
        ctx = ctx or {}
        model = req.model
        if not model:
            return PolicyResult.allow()
        portal_user = ctx.get('portal_user')
        if not portal_user:
            return PolicyResult.deny('ACCOUNT_DISABLED', 'Account disabled', 403)
        allowed = self.allowed_models_loader(int(portal_user['id']))
        if model not in allowed:
            return PolicyResult.deny('MODEL_NOT_ALLOWED', f'Model not allowed: {model}', 403, model=model)
        return PolicyResult.allow(model=model)


class PolicyPipeline:
    def __init__(self, policies):
        self.policies = list(policies)

    def run(self, req: 'NormalizedRequest', ctx: dict[str, Any] | None = None) -> PolicyResult:
        merged = dict(ctx or {})
        for policy in self.policies:
            result = policy.evaluate(req, merged)
            if result.context:
                merged.update(result.context)
            if not result.allowed:
                return PolicyResult(
                    allowed=False,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    http_status=result.http_status,
                    context=merged,
                )
        return PolicyResult.allow(**merged)


@dataclass(frozen=True)
class NormalizedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes
    client_ip: str
    request_id: str
    api_key: str = ''
    # Valid only when body has already been read and supplied to normalize_request().
    model: str = ''


@dataclass(frozen=True)
class AccessLogRecord:
    user_id: int | None = None
    key_id: int | None = None
    ip: str = ''
    method: str = ''
    path: str = ''
    model: str = ''
    status: int = 0
    error_code: str = ''
    latency_ms: int = 0
    request_id: str = ''

    def insert_values(self, created_at: int):
        return (
            self.user_id, self.key_id, self.ip, self.method, self.path,
            self.model, self.status, self.error_code, self.latency_ms,
            created_at, self.request_id,
        )


def build_access_log_record(
    user_id=None, key_id=None, ip='', method='', path='', model='',
    status=0, error_code='', latency_ms=0, request_id='',
) -> AccessLogRecord:
    return AccessLogRecord(
        user_id=user_id,
        key_id=key_id,
        ip=ip or '',
        method=method or '',
        path=path or '',
        model=model or '',
        status=int(status or 0),
        error_code=error_code or '',
        latency_ms=int(latency_ms or 0),
        request_id=request_id or '',
    )


class AccessLogWriter(Protocol):
    def write(self, record: AccessLogRecord, created_at: int) -> None:
        ...


def write_access_log_record(writer: AccessLogWriter, record: AccessLogRecord, created_at: int) -> None:
    writer.write(record, created_at)


def header_get(headers: Mapping[str, str], name: str, default: str = '') -> str:
    lname = name.lower()
    for key, value in headers.items():
        if key.lower() == lname:
            return value
    return default


def make_request_id_from_headers(headers: Mapping[str, str] | None = None) -> str:
    headers = headers or {}
    incoming = (header_get(headers, REQUEST_ID_HEADER) or header_get(headers, 'X-Request-ID')).strip()
    if incoming and REQUEST_ID_RE.fullmatch(incoming):
        return incoming[:80]
    return 'req_' + secrets.token_hex(12)


def client_ip_from_headers(headers: Mapping[str, str], fallback_ip: str = '') -> str:
    xff = header_get(headers, 'X-Forwarded-For')
    first = xff.split(',', 1)[0].strip() if xff else ''
    return first or fallback_ip


def extract_bearer_token(headers: Mapping[str, str]) -> str:
    auth = header_get(headers, 'Authorization')
    if not auth.lower().startswith('bearer '):
        return ''
    parts = auth.split(None, 1)
    return parts[1].strip() if len(parts) == 2 else ''


def model_from_json_body(body: bytes, content_type: str = '') -> str:
    if not body or content_type.split(';', 1)[0].lower() != 'application/json':
        return ''
    try:
        data = json.loads(body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ''
    if not isinstance(data, dict):
        return ''
    model = data.get('model') or ''
    return str(model) if model else ''


def normalize_request(method: str, path: str, headers: Mapping[str, str], body: bytes, fallback_ip: str = '') -> NormalizedRequest:
    copied = {str(k): str(v) for k, v in headers.items()}
    return NormalizedRequest(
        method=method,
        path=path,
        headers=copied,
        body=body or b'',
        client_ip=client_ip_from_headers(copied, fallback_ip),
        request_id=make_request_id_from_headers(copied),
        api_key=extract_bearer_token(copied),
        model=model_from_json_body(body or b'', header_get(copied, 'Content-Type')),
    )


def path_without_query(path: str) -> str:
    return str(path or '').split('?', 1)[0]


def is_models_request(method: str, path: str) -> bool:
    return str(method or '').upper() in ('GET', 'HEAD') and path_without_query(path).rstrip('/') == '/v1/models'


def build_upstream_url(upstream_base: str, request_path: str) -> str:
    return str(upstream_base or '').rstrip('/') + str(request_path or '')


def build_model_list_payload(models) -> bytes:
    payload = {
        'object': 'list',
        'data': [{'id': m, 'object': 'model', 'created': 0, 'owned_by': 'nw-api'} for m in sorted(models)],
    }
    return json.dumps(payload, ensure_ascii=False).encode('utf-8')


def proxy_request_headers(headers: Mapping[str, str], request_id: str) -> dict[str, str]:
    out = {
        key: value
        for key, value in headers.items()
        if key.lower() not in ('host', 'content-length', 'connection', 'accept-encoding')
    }
    out[REQUEST_ID_HEADER] = request_id
    return out


def should_forward_response_header(name: str) -> bool:
    return name.lower() not in HOP_BY_HOP_HEADERS


def upstream_http_error_code(http_status: int) -> str:
    if http_status == 429:
        return 'UPSTREAM_RATE_LIMIT'
    if http_status in (502, 503, 504):
        return 'UPSTREAM_UNAVAILABLE'
    return 'UPSTREAM_HTTP_ERROR'


def should_chunk_downstream(content_length, method: str) -> bool:
    return content_length is None and method != 'HEAD'


def encode_chunk(chunk: bytes) -> bytes:
    return (f'{len(chunk):X}\r\n').encode('ascii') + chunk + b'\r\n'

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
from dataclasses import dataclass
from typing import Mapping

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
class NormalizedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes
    client_ip: str
    request_id: str
    api_key: str = ''
    model: str = ''


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


def should_chunk_downstream(content_length, method: str) -> bool:
    return content_length is None and method != 'HEAD'


def encode_chunk(chunk: bytes) -> bytes:
    return (f'{len(chunk):X}\r\n').encode('ascii') + chunk + b'\r\n'

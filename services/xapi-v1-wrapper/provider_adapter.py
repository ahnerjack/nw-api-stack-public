#!/usr/bin/env python3
"""Minimal provider adapter layer for NW-API stage 11.

The first adapter wraps the existing OpenAI-compatible upstream behavior. It is
small on purpose: prepare headers, send with urllib, and parse usage from JSON
responses when available. Streaming stays pass-through and reports no_usage.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Mapping, Optional


@dataclass(frozen=True)
class UsageSnapshot:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    status: str = 'no_usage'
    raw_usage_json: str = ''


@dataclass(frozen=True)
class ProviderResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    error_code: str = ''


class OpenAICompatibleAdapter:
    provider_name = 'sub2api'

    def __init__(self, upstream_base: str, timeout: float = 10):
        self.upstream_base = str(upstream_base or '').rstrip('/')
        self.timeout = timeout

    def build_url(self, path: str) -> str:
        return self.upstream_base + str(path or '')

    def request(self, method: str, path: str, headers: Mapping[str, str], body: bytes | None = None) -> ProviderResponse:
        req = urllib.request.Request(
            self.build_url(path),
            data=(body if str(method).upper() not in ('GET', 'HEAD') else None),
            headers=dict(headers or {}),
            method=str(method).upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = b'' if str(method).upper() == 'HEAD' else resp.read()
                return ProviderResponse(resp.status, dict(resp.headers.items()), payload, parse_usage_from_body(payload, resp.headers.get('Content-Type', '')))
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            return ProviderResponse(exc.code, dict(exc.headers.items()), payload, parse_usage_from_body(payload, exc.headers.get('Content-Type', '')), 'UPSTREAM_HTTP_ERROR')


def parse_usage_from_body(body: bytes, content_type: str = '') -> UsageSnapshot:
    ctype = str(content_type or '').split(';', 1)[0].lower()
    if ctype and ctype != 'application/json':
        return UsageSnapshot(status='no_usage')
    try:
        data = json.loads((body or b'').decode('utf-8') or '{}')
    except Exception:
        return UsageSnapshot(status='no_usage')
    usage = data.get('usage') if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return UsageSnapshot(status='no_usage')
    prompt = int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0)
    completion = int(usage.get('completion_tokens') or usage.get('output_tokens') or 0)
    total = int(usage.get('total_tokens') or (prompt + completion))
    return UsageSnapshot(prompt, completion, total, 'reported', json.dumps(usage, ensure_ascii=False, sort_keys=True))

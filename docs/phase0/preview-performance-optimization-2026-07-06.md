# Phase0 preview performance optimization report

Date: 2026-07-06
Scope: preview stack deployment only (`10.0.1.66:9088`, phase0 systemd units). Formal/public production deployment was not changed during this work. Some code changes are in shared source files and would affect a future formal release if packaged/deployed; preview-only behavior is gated by phase0 service environment variables.

## Summary

The preview stack's concurrent P95 latency was reduced by removing avoidable request-time work and making the `/v1` preview gateway behave closer to an OpenAI-compatible streaming endpoint.

Key changes:
- Raised stdlib HTTP server listen backlog to 128 for preview gateway, portal mock, data mock, and wrapper.
- Moved wrapper access-log schema migration out of every request path.
- Added `XAPI_WRAPPER_LOG_ACCESS=0` for phase0 preview wrapper to avoid SQLite write contention during preview load tests.
- Added short TTL key verification cache for preview wrapper (`XAPI_KEY_VERIFY_CACHE_TTL_SECONDS=10`).
- Removed per-request upstream TCP probe before forwarding; direct upstream request now handles connection failures.
- Added `/v1` streaming proxy in preview gateway; `/nv-api` still uses buffered HTML/Cookie rewriting.
- Fixed `HEAD /v1/models` to return 200 with no response body.
- Added preview-only mock chat (`XAPI_WRAPPER_MOCK_CHAT=1`) so valid preview keys can exercise non-stream and stream chat without leaking preview keys to a real upstream.
- Added repeatable benchmark script: `scripts/phase0_preview_perf.py`.

## Verified results

Remote smoke and compatibility checks after deployment:
- `GET /` via 9088: 200
- `GET /nv-api/` via 9088: 200
- Invalid `GET /v1/models`: 401 `INVALID_API_KEY`
- Valid `GET /v1/models`: 200 model list with `X-Request-Id`
- `HEAD /v1/models`: 200, no body
- Invalid chat: 401 `INVALID_API_KEY`
- Valid non-stream chat: 200 mock chat completion
- Valid stream chat: 200 SSE, `Transfer-Encoding: chunked`, includes `data: [DONE]`

Regression tests:
- `tests/phase1/test_gateway_core.py`: 22/22 OK
- `tests/phase0/test_v1_wrapper_regression.py`: 15/15 OK
- Local preview gateway streaming test: first SSE event around 0.58ms in mock test

Latest external 30-concurrency probe after compatibility fixes:
- `/`: P95 40.68ms
- `/nv-api/`: P95 55.22ms
- invalid `/v1/models`: P95 49.38ms
- invalid `/v1/chat/completions`: P95 39.60ms

Internal remote probe after compatibility fixes:
- gateway invalid `/v1/models`: P95 21.06ms
- wrapper invalid `/v1/models`: P95 19.73ms
- data verify invalid: P95 8.79ms
- data health: P95 6.59ms

Earlier baseline during investigation showed invalid `/v1/models` and invalid chat P95 in the 300ms+ range under 30 concurrency. The main improvement came from removing synchronous SQLite access logging from the preview hot path and increasing listen backlog.

## Deployment and rollback notes

Preview backups created on `10.0.1.66`:
- `/tmp/nwapi-opt3-backup-20260706-165438`
- `/tmp/nwapi-opt4-backup-20260706-172122`
- `/tmp/nwapi-stream-backup-20260706-190119`
- `/tmp/nwapi-compat-backup-20260706-204551`

Rollback should restore the affected files from the latest backup and restart only the phase0 preview units.

## Safety notes

- `XAPI_WRAPPER_MOCK_CHAT=1` must remain preview-only.
- `XAPI_WRAPPER_LOG_ACCESS=0` is preview-only and should not be copied into production unless intentionally replacing access logs with an async writer.
- Key verify TTL is set to 10 seconds for preview; production needs explicit invalidation or a carefully chosen TTL.
- The `/nv-api` portal path is intentionally still buffered because it rewrites HTML paths and cookie paths.

## Repeatable benchmark

Run from the preview host:

```bash
python3 /opt/nw-api-phase0-preview/repo/scripts/phase0_preview_perf.py --host 127.0.0.1 --total 100 --concurrency 30 --include-internal
```

Run from another LAN host against public preview entrypoints only:

```bash
python3 scripts/phase0_preview_perf.py --host 10.0.1.66 --total 100 --concurrency 30
```

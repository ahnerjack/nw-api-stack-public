# Stage 5 Gateway Core extraction

Date: 2026-07-07
Formal production updated: no

## Scope

Small, behavior-preserving Gateway Core extraction for `/v1` wrapper routing helpers.

## Changes

- Added pure helpers to `services/xapi-v1-wrapper/gateway_core.py`:
  - `path_without_query(path)`
  - `is_models_request(method, path)`
  - `build_upstream_url(upstream_base, request_path)`
- Replaced wrapper inline string logic with these helpers in `services/xapi-v1-wrapper/xapi_v1_wrapper.py`.
- Added unit coverage in `tests/phase1/test_gateway_core.py`.

## Invariants checked

- `body = self.read_body()` still happens only after IP/Auth policy passes.
- `/v1/models` still returns before reading body.
- `log_access()` remains in wrapper, not in Gateway Core.
- New helpers are pure string helpers with no DB/network/filesystem side effects.

## Independent review

OpenCode reviewed the diff and found no blocker.
Confidence: high.

## Verification

Local:

- `py_compile`: OK
- `tests/phase1/test_gateway_core.py`: 23/23 OK
- `tests/phase0/test_v1_wrapper_regression.py`: 15/15 OK
- `tests/phase0/test_release_versioning.py`: 2/2 OK

Preview deploy:

- Deployed to `10.0.1.66:9088` isolated preview stack.
- `nginx`: active
- `xapi-data-phase0-preview`: active
- `xapi-portal-phase0-preview`: active
- `xapi-v1-wrapper-phase0-preview`: active
- legacy `nw-api-phase0-preview`: inactive

Preview smoke:

- `/`: 200
- `/nv-api/`: 200
- `/nv-api`: 302
- `/nv-api/login`: 200
- `/v1/models` invalid: 401
- `/v1/chat/completions` invalid: 401
- `/bad-path`: 404
- root-link leaks: 0
- upstream leaks: none

Preview performance, 100 requests / 30 concurrency:

- `/`: P95 110.84ms, errors 0
- `/nv-api/`: P95 63.22ms, errors 0
- `/v1/models` invalid: P95 36.33ms, errors 0
- `/v1/chat/completions` invalid: P95 33.14ms, errors 0

Logs:

- Last 10 minutes warning/error: none

## Status

Stage 5 is complete for this batch. No formal production runtime was changed.

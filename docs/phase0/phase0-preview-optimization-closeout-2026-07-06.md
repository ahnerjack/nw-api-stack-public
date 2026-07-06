# NW-API phase0 preview optimization closeout

Date: 2026-07-06
Final commit: d227937
Branch: public-sanitized
Production updated: no
GitHub Release published: no

## Completed

1. Optimized phase0 preview stack latency.
   - Raised stdlib HTTP server listen backlog to 128.
   - Reduced wrapper hot-path SQLite work.
   - Disabled wrapper access logging only for phase0 preview.
   - Added key verify TTL support, enabled only in phase0 preview.
   - Removed wrapper upstream pre-connect probe.
   - Added `/v1` streaming proxy in preview gateway.
   - Fixed `HEAD /v1/models`.
   - Added preview-only mock chat.

2. Added repeatable performance probe.
   - `scripts/phase0_preview_perf.py`

3. Documented release/version safety.
   - `docs/release/versioning.md`
   - `docs/release/production-update-gate.md`
   - `docs/release/README.md`

4. Built and archived a dry-run RC package.
   - Version: `V0.0.2-rc.1`
   - SHA256: `bc7a9408986ab00a10eff943d6404e43fea1b396bf5a731a2d3677a7f31abc6a`
   - NAS: `/volume1/hermes/projects/nw-api-stack-public/release-dryruns/2026-07-06`

## Final verification

- Local git HEAD: `d227937`
- Remote `origin/public-sanitized`: `d227937`
- Preview services on `10.0.1.66`: active
  - `nw-api-phase0-preview`
  - `xapi-v1-wrapper-phase0-preview`
  - `xapi-data-phase0-preview`
  - `xapi-portal-phase0-preview`
- Listening ports:
  - `9088` backlog 128
  - `19080` backlog 128
  - `19081` backlog 128
  - `19082` backlog 128
- Smoke:
  - `GET /` on 9088: 200
  - invalid `GET /v1/models` on 9088: 401
- NAS dry-run artifact present and checksum verified.

## Test history

- `tests/phase1/test_gateway_core.py`: 22/22 OK
- `tests/phase0/test_v1_wrapper_regression.py`: 15/15 OK
- `tests/phase0/test_release_versioning.py`: 2/2 OK
- Secret scan on release diff: private_key=0, api_key=0, bearer_long=0

## Status

This phase is complete. Formal production release has not started. If a production update is requested later, follow `docs/release/production-update-gate.md` before publishing or applying any release.

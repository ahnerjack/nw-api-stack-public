# NW-API Stage 3-7 final closeout

Date: 2026-07-07
Branch: public-sanitized
Formal production updated: no
Preview target: `10.0.1.66:9088`

## Completed stages

### Stage 3 — release candidate validation

- Built and inspected `V0.0.2-rc.1` formal candidate package.
- Confirmed package does not include preview-only nginx/9088/mock/test artifacts.
- Ran secret scan and local regression.
- Archived RC validation to NAS.

### Stage 4 — formal online-update path hardening

- Added missing Release asset updater:
  - `scripts/preview_release_update.py`
- Added missing package deployer / activation helper:
  - `scripts/deploy-preview-package.sh`
- Added both scripts into formal package manifest.
- Made Release mode fail fast if updater/deployer scripts are missing.
- Fixed `/version-status` Release-mode default behavior so it checks GitHub Release instead of local Git on first open.
- Added formal update env example keys to `systemd/xapi-portal.env.example`.
- Built `V0.0.2-rc.2` dry-run package and verified package is self-contained.

### Stage 5 — Gateway Core extraction

- Added pure route helpers to `gateway_core.py`:
  - `path_without_query()`
  - `is_models_request()`
  - `build_upstream_url()`
- Replaced inline wrapper routing/url logic with core helpers.
- Added unit tests.
- Verified body-read invariant: invalid/missing auth still rejects before reading POST body.
- Deployed to isolated preview and verified.

### Stage 6 — usage ledger and pricing autonomy

- Made portal price sync accept both dict-shaped backend pricing and legacy list-shaped preview pricing.
- Added `/xapi-data/usage-ledger` backed by Sub2API `usage_logs`.
- Added preview mock `/xapi-data/usage-ledger` returning isolated empty data.
- Added user-facing usage ledger CSV export.
- No real balances, quotas, or billing tables changed.

### Stage 7 — final productization gate

- Built final candidate dry-run package:
  - `V0.0.2-rc.3`
  - `nw-api-V0.0.2-rc.3-linux-amd64.tar.gz`
  - SHA256: `86d9afcc5df8cc96bd07646bccb2e95c4c8d36d51be2f594cddae5f860fee816`
- Package gate:
  - forbidden preview/test/doc artifacts: 0
  - required updater/deployer/core/data/portal files: present
- Final preview smoke and performance passed.

## Final verification

Local checks:

- `py_compile`: OK
- shell syntax checks: OK
- `tests/phase1/test_gateway_core.py`: 23/23 OK
- `tests/phase0/test_v1_wrapper_regression.py`: 15/15 OK
- `tests/phase0/test_release_versioning.py`: 2/2 OK
- secret scan on diff:
  - private_key: 0
  - api_key: 0
  - bearer_long: 0

Preview services:

- `nginx`: active
- `xapi-data-phase0-preview`: active
- `xapi-portal-phase0-preview`: active
- `xapi-v1-wrapper-phase0-preview`: active
- legacy `nw-api-phase0-preview`: inactive

Preview route smoke:

- `/`: 200
- `/nv-api/`: 200
- `/nv-api`: 302
- `/nv-api/login`: 200
- `/v1/models` invalid: 401
- `/v1/chat/completions` invalid: 401
- `/bad-path`: 404
- root-link leaks: 0
- upstream leaks: none

Preview performance, 120 requests / 30 concurrency:

- `/`: P95 38.94ms, errors 0
- `/nv-api/`: P95 54.58ms, errors 0
- `/v1/models` invalid: P95 42.01ms, errors 0
- `/v1/chat/completions` invalid: P95 35.47ms, errors 0

Logs:

- Last 15 minutes preview warning/error: none

## External agent status

- OpenCode successfully reviewed Stage 5 Gateway Core extraction and found no blocker.
- Codex final review timed out and produced no final artifact; not treated as evidence.

## Formal production state

No formal production deploy/update was performed.
This work is preview-verified and package-dry-run verified only.

## Next step if formal update is desired

Cut and publish a real formal tag/release such as `V0.0.2`, upload the verified package and `checksums.txt`, then use the formal site's own update flow or an explicitly authorized formal update procedure.

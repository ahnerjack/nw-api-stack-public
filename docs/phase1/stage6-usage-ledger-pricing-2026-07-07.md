# Stage 6 usage, ledger, and pricing autonomy

Date: 2026-07-07
Formal production updated: no

## Scope

Move NW-API one step closer to self-owned usage/billing/pricing surfaces while keeping Sub2API as the backend source of truth for this batch.

## Changes

- `services/xapi-portal/xapi_portal.py`
  - Added `normalize_pricing_item()` so the portal can consume both dict-shaped and legacy list-shaped `/xapi-data/pricing` responses.
  - Fixed pricing sync robustness for preview/mock data and backend data.
  - Added user usage-ledger CSV export: `export.csv?type=usage_ledger`.
  - Added a visible "导出明细流水 CSV" action on `/usage`.
- `services/xapi-data/xapi_data_api.py`
  - Added `/xapi-data/usage-ledger` endpoint backed by Sub2API `usage_logs`.
  - Exposes id, time, model, input/cache/output tokens, total_cost, actual_cost, request_id.
- `services/xapi-data-mock/phase0_data_mock.py`
  - Added preview-safe `/xapi-data/usage-ledger` mock endpoint returning empty isolated ledger.

## Boundary

- Source of truth remains Sub2API `usage_logs` / pricing tables.
- NW-API now has a clearer own-facing ledger/export surface.
- No real billing tables or production balances were changed.
- Preview mock remains isolated from formal Sub2API mutations.

## Verification

Local:

- `py_compile`: OK
  - portal
  - xapi-data
  - phase0 data mock
- Regression:
  - phase1 gateway core: 23/23 OK
  - phase0 wrapper regression: 15/15 OK
  - release versioning: 2/2 OK

Preview deploy:

- Deployed to isolated preview `10.0.1.66:9088`.
- `/xapi-data/usage-ledger?uid=1`: OK, empty mock ledger.
- `/xapi-data/pricing`: OK, legacy list-shaped mock pricing still accepted.

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

- `/`: P95 108.46ms, errors 0
- `/nv-api/`: P95 52.11ms, errors 0
- `/v1/models` invalid: P95 35.25ms, errors 0
- `/v1/chat/completions` invalid: P95 32.98ms, errors 0

Logs:

- Last 10 minutes warning/error: none

## Status

Stage 6 is complete for this batch. No formal production runtime was changed.

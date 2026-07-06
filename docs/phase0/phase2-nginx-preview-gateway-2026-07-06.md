# Phase2 preview gateway migration to nginx

Date: 2026-07-06
Scope: phase0 preview only (`10.0.1.66:9088`). Formal production was not updated.

## Goal

Replace the Python preview entrypoint on `:9088` with nginx, while keeping the existing phase0 preview backend services:

- portal: `127.0.0.1:19080`
- mock data: `127.0.0.1:19081`
- v1 wrapper: `127.0.0.1:19082`

## Delivered

- Added nginx preview config template:
  - `nginx/nw-api-phase0-preview-nginx.conf.template`
- Added deploy/cutover helper:
  - `scripts/deploy-phase0-nginx-preview.sh`
- Updated preview host deploy script so future preview deploys keep nginx as the `:9088` entrypoint:
  - `scripts/deploy-phase0-preview-host.sh`
- Updated perf probe to support testing alternate public gateway ports:
  - `scripts/phase0_preview_perf.py --port 9089`

## Deployment performed

1. PoC deployed on `:9089`.
2. PoC verified against `/`, `/nv-api/`, `/v1/models`, `/v1/chat/completions`, and 404 fallback.
3. Cutover performed to `:9088`.
4. Legacy Python gateway service was stopped and disabled:
   - `nw-api-phase0-preview`: inactive/disabled
5. nginx now owns `0.0.0.0:9088`.

## Final service state

- `nginx`: active
- `xapi-data-phase0-preview`: active
- `xapi-portal-phase0-preview`: active
- `xapi-v1-wrapper-phase0-preview`: active
- `nw-api-phase0-preview`: inactive/disabled

## Functional verification

On preview host:

- `/`: 200
- `/nv-api/`: 200
- `/nv-api`: 302 to `/nv-api/`
- `/v1/models` with invalid key: 401
- `/no-such-path`: 404
- `/nv-api/` HTML root-link leak count: 0

## Performance verification

LAN probe after cutover, 100 requests, 30 concurrency:

- `gateway_root`: p95 42.85 ms, errors 0
- `gateway_portal`: p95 52.33 ms, errors 0
- `gateway_models_invalid`: p95 43.35 ms, errors 0
- `gateway_chat_invalid`: p95 43.84 ms, errors 0

Remote loopback probe after cutover, 100 requests, 30 concurrency:

- `/nv-api/`: p95 22.80 ms
- `/v1/models` invalid: p95 19.84 ms
- `/v1/chat/completions` invalid: p95 20.99 ms
- wrapper invalid direct: p95 20.74 ms
- data verify invalid direct: p95 8.86 ms
- data health direct: p95 7.14 ms

Loopback `/` has a repeatable Nginx accept/worker scheduling outlier under the synthetic one-shot connection pattern: p50 ~1 ms and p95 ~438 ms, while LAN `/` p95 stays ~43 ms. The API/portal paths that matter for preview usage are stable and faster than the Python gateway.

## Review notes

OpenCode reviewed the initial PoC scripts and found cutover risks:

- cutover defaulted to `9089` instead of explicitly using `9088`;
- nginx reload happened before stopping the old Python listener;
- rollback path was not explicit;
- `/v1/models` smoke did not assert 401.

These were fixed before cutover:

- `cutover` defaults to `9088` and rejects other ports;
- legacy Python gateway is stopped before nginx reload on cutover;
- rollback trap restores nginx config and restarts the Python gateway if needed;
- invalid-key smoke now asserts HTTP 401.

Codex/Claude were not reliable for final phase2 review in this session: Codex did not write the requested artifact before timeout/auth noise; Claude failed due prompt length. OpenCode produced the effective review.

## Rollback

If the nginx entrypoint fails, restore the legacy Python gateway:

```bash
sudo rm -f /etc/nginx/sites-enabled/nw-api-phase0-preview-nginx
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl enable nw-api-phase0-preview
sudo systemctl start nw-api-phase0-preview
curl -fsS http://127.0.0.1:9088/ >/dev/null
```

Timestamped nginx backups are also created under:

```text
/tmp/nwapi-phase2-nginx-backup-*
```

The cutover backup used during final deployment:

```text
/tmp/nwapi-phase2-nginx-backup-20260706-223907
```

## Status

Phase2 preview gateway migration is complete. Formal production remains untouched.

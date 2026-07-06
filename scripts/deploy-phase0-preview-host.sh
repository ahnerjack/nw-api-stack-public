#!/usr/bin/env bash
set -euo pipefail

ROOT=${NW_API_PHASE0_PREVIEW_ROOT:-/opt/nw-api-phase0-preview}
PORT=${NW_API_PHASE0_PREVIEW_PORT:-9088}
REPO_SRC=$(cd "$(dirname "$0")/.." && pwd)

install -d "$ROOT" "$ROOT/state" "$ROOT/logs" "$ROOT/repo" "$ROOT/xapi-portal" "$ROOT/xapi-v1-wrapper" "$ROOT/xapi-data-mock" "$ROOT/preview-nav"

install -m 0644 "$REPO_SRC/services/xapi-portal/xapi_portal.py" "$ROOT/xapi-portal/xapi_portal.py"
install -m 0755 "$REPO_SRC/services/xapi-v1-wrapper/xapi_v1_wrapper.py" "$ROOT/xapi-v1-wrapper/xapi_v1_wrapper.py"
install -m 0644 "$REPO_SRC/services/xapi-v1-wrapper/gateway_core.py" "$ROOT/xapi-v1-wrapper/gateway_core.py"
install -m 0755 "$REPO_SRC/services/xapi-data-mock/phase0_data_mock.py" "$ROOT/xapi-data-mock/phase0_data_mock.py"
install -m 0755 "$REPO_SRC/services/preview-nav/preview_gateway.py" "$ROOT/preview-nav/preview_gateway.py"

rsync -a --delete --exclude '.git' --exclude '.venv*' --exclude '__pycache__' "$REPO_SRC/" "$ROOT/repo/"

install -m 0644 "$REPO_SRC/systemd/xapi-data-phase0-preview.service" /etc/systemd/system/xapi-data-phase0-preview.service
install -m 0644 "$REPO_SRC/systemd/xapi-portal-phase0-preview.service" /etc/systemd/system/xapi-portal-phase0-preview.service
install -m 0644 "$REPO_SRC/systemd/xapi-v1-wrapper-phase0-preview.service" /etc/systemd/system/xapi-v1-wrapper-phase0-preview.service
# Keep the legacy Python gateway unit available for rollback/manual comparison,
# but the phase2 preview entrypoint is nginx on :9088.
install -m 0644 "$REPO_SRC/systemd/nw-api-phase0-preview.service" /etc/systemd/system/nw-api-phase0-preview.service

python3 -m py_compile \
  "$ROOT/xapi-portal/xapi_portal.py" \
  "$ROOT/xapi-v1-wrapper/xapi_v1_wrapper.py" \
  "$ROOT/xapi-v1-wrapper/gateway_core.py" \
  "$ROOT/xapi-data-mock/phase0_data_mock.py" \
  "$ROOT/preview-nav/preview_gateway.py"

systemctl daemon-reload
systemctl restart xapi-data-phase0-preview xapi-portal-phase0-preview xapi-v1-wrapper-phase0-preview
systemctl enable xapi-data-phase0-preview xapi-portal-phase0-preview xapi-v1-wrapper-phase0-preview >/dev/null 2>&1 || true

NW_API_PHASE0_NGINX_PORT="$PORT" "$REPO_SRC/scripts/deploy-phase0-nginx-preview.sh" cutover

systemctl is-active xapi-data-phase0-preview
systemctl is-active xapi-portal-phase0-preview
systemctl is-active xapi-v1-wrapper-phase0-preview
systemctl is-active nginx
systemctl is-active nw-api-phase0-preview && { echo "legacy Python preview gateway should be stopped" >&2; exit 1; } || true
ss -lntp | grep ":$PORT" || true

# HTTP smoke checks
curl -fsS http://127.0.0.1:19081/xapi-data/health >/dev/null
curl -fsS http://127.0.0.1:9088/ >/dev/null
curl -fsS http://127.0.0.1:9088/nv-api/ >/dev/null

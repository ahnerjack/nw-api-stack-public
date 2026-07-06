#!/usr/bin/env bash
set -euo pipefail

MODE=${1:-poc}
if [[ $MODE != "poc" && $MODE != "cutover" ]]; then
  echo "usage: $0 [poc|cutover]" >&2
  exit 2
fi

if [[ -n ${NW_API_PHASE0_NGINX_PORT:-} ]]; then
  PORT=$NW_API_PHASE0_NGINX_PORT
elif [[ $MODE == "cutover" ]]; then
  PORT=9088
else
  PORT=9089
fi

if [[ $MODE == "cutover" && $PORT != "9088" ]]; then
  echo "cutover must use port 9088; got $PORT" >&2
  exit 2
fi

REPO_SRC=$(cd "$(dirname "$0")/.." && pwd)
TEMPLATE="$REPO_SRC/nginx/nw-api-phase0-preview-nginx.conf.template"
AVAILABLE=/etc/nginx/sites-available/nw-api-phase0-preview-nginx
ENABLED=/etc/nginx/sites-enabled/nw-api-phase0-preview-nginx
BACKUP_DIR=/tmp/nwapi-phase2-nginx-backup-$(date +%Y%m%d-%H%M%S)
STOPPED_PREVIEW=0

restore_on_error() {
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    return 0
  fi
  echo "deploy failed, attempting rollback from $BACKUP_DIR" >&2
  if [[ -f "$BACKUP_DIR/available" ]]; then
    cp -a "$BACKUP_DIR/available" "$AVAILABLE"
    ln -sfn "$AVAILABLE" "$ENABLED"
  else
    rm -f "$AVAILABLE" "$ENABLED"
  fi
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  if [[ $STOPPED_PREVIEW -eq 1 ]]; then
    systemctl enable nw-api-phase0-preview >/dev/null 2>&1 || true
    systemctl start nw-api-phase0-preview || true
  fi
  exit "$rc"
}
trap restore_on_error ERR

if [[ ! -f $TEMPLATE ]]; then
  echo "missing template: $TEMPLATE" >&2
  exit 1
fi

if ! nginx -V 2>&1 | grep -q -- '--with-http_sub_module'; then
  echo "nginx was built without http_sub_module; cannot use sub_filter preview rewrite" >&2
  exit 1
fi

install -d "$BACKUP_DIR"
if [[ -f $AVAILABLE ]]; then cp -a "$AVAILABLE" "$BACKUP_DIR/available"; fi
if [[ -L $ENABLED || -f $ENABLED ]]; then cp -a "$ENABLED" "$BACKUP_DIR/enabled"; fi

if [[ $MODE == "cutover" ]]; then
  systemctl stop nw-api-phase0-preview || true
  STOPPED_PREVIEW=1
fi

export NW_API_PHASE0_NGINX_PORT=$PORT
envsubst '${NW_API_PHASE0_NGINX_PORT}' < "$TEMPLATE" > /tmp/nw-api-phase0-preview-nginx.conf
install -m 0644 /tmp/nw-api-phase0-preview-nginx.conf "$AVAILABLE"
ln -sfn "$AVAILABLE" "$ENABLED"
nginx -t
systemctl reload nginx

if [[ $MODE == "cutover" ]]; then
  systemctl disable nw-api-phase0-preview >/dev/null 2>&1 || true
fi

systemctl is-active nginx
ss -lntp | grep ":$PORT" || true
curl -fsS "http://127.0.0.1:$PORT/" >/dev/null
curl -fsS "http://127.0.0.1:$PORT/nv-api/" >/dev/null
models_code=$(curl -sS -o /dev/null -w "%{http_code}" -H 'Authorization: Bearer invalid' "http://127.0.0.1:$PORT/v1/models")
if [[ $models_code != "401" ]]; then
  echo "unexpected /v1/models invalid-key status: $models_code" >&2
  exit 1
fi
echo "models_invalid=$models_code"
echo "mode=$MODE port=$PORT backup=$BACKUP_DIR"

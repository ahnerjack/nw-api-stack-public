#!/usr/bin/env bash
set -euo pipefail

ROOT=/opt/nw-api-release
ACTIVATE=""
FORCE=0
RUNTIME=auto
ASSET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --activate) ACTIVATE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --runtime) RUNTIME="$2"; shift 2 ;;
    --runtime=*) RUNTIME="${1#*=}"; shift ;;
    --) shift; break ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) ASSET="$1"; shift ;;
  esac
done

if [ -n "$ACTIVATE" ]; then
  case "$ACTIVATE" in */*|*..*|'') echo "unsafe activate target" >&2; exit 2 ;; esac
  test -d "$ROOT/releases/$ACTIVATE" || { echo "release not found: $ACTIVATE" >&2; exit 1; }
  ln -sfn "$ROOT/releases/$ACTIVATE" "$ROOT/current"
  if [ -f "$ROOT/current/scripts/deploy-aliyun.sh" ]; then
    cd "$ROOT/current"
    bash scripts/deploy-aliyun.sh
  fi
  exit 0
fi

if [ -z "$ASSET" ]; then
  echo "usage: $0 [--root DIR] [--force] [--runtime auto] ASSET.tar.gz" >&2
  exit 2
fi

test -f "$ASSET" || { echo "asset not found: $ASSET" >&2; exit 1; }
mkdir -p "$ROOT/releases"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

tar -xzf "$ASSET" -C "$TMP"
TOP=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
test -n "$TOP" || { echo "empty package" >&2; exit 1; }
test -f "$TOP/VERSION" || { echo "VERSION missing" >&2; exit 1; }
test -f "$TOP/manifest.json" || { echo "manifest.json missing" >&2; exit 1; }
VERSION=$(tr -d '\r\n ' < "$TOP/VERSION")
case "$VERSION" in */*|*..*|'') echo "unsafe version" >&2; exit 2 ;; esac
DEST="$ROOT/releases/$VERSION"
if [ -e "$DEST" ] && [ "$FORCE" != 1 ]; then
  echo "release exists: $DEST; pass --force" >&2
  exit 1
fi
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$TOP" "$DEST"
ln -sfn "$DEST" "$ROOT/current"

cd "$DEST"
python3 -m py_compile services/xapi-portal/xapi_portal.py services/xapi-data/xapi_data_api.py services/xapi-v1-wrapper/xapi_v1_wrapper.py services/xapi-v1-wrapper/gateway_core.py
bash scripts/deploy-aliyun.sh
bash scripts/deploy-sub2api-host.sh || true

systemctl is-active --quiet xapi-portal
if systemctl list-unit-files | grep -q '^xapi-v1-wrapper\.service'; then
  systemctl is-active --quiet xapi-v1-wrapper
fi
if systemctl list-unit-files | grep -q '^xapi-data\.service'; then
  systemctl is-active --quiet xapi-data
fi

echo "activated $VERSION at $DEST runtime=$RUNTIME"

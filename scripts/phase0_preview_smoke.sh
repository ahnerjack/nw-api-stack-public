#!/usr/bin/env bash
set -euo pipefail

HOST=${1:-127.0.0.1}
PORT=${2:-9088}
BASE="http://${HOST}:${PORT}"
TMP=${TMPDIR:-/tmp}/nwapi-phase0-smoke-$$
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

check_code() {
  local label=$1
  local expected=$2
  shift 2
  local code
  code=$(curl -sS -o "$TMP/${label}.out" -w '%{http_code}' "$@")
  if [[ "$code" != "$expected" ]]; then
    echo "FAIL $label expected=$expected got=$code" >&2
    sed -n '1,40p' "$TMP/${label}.out" >&2 || true
    exit 1
  fi
  echo "OK $label $code"
}

check_code root 200 "$BASE/"
check_code portal 200 "$BASE/nv-api/"
check_code portal_redirect 302 "$BASE/nv-api"
check_code login 200 "$BASE/nv-api/login"
check_code models_invalid 401 -H 'Authorization: Bearer invalid' "$BASE/v1/models"
check_code chat_invalid 401 \
  -H 'Authorization: Bearer invalid' \
  -H 'Content-Type: application/json' \
  --data '{"model":"gpt-5.5","messages":[]}' \
  "$BASE/v1/chat/completions"
check_code not_found 404 "$BASE/bad-path"

curl -sS "$BASE/nv-api/" > "$TMP/portal.html"
root_link_leaks=$(grep -Eo '(href|action|src)="/[^"]+' "$TMP/portal.html" | grep -vcE '="/nv-api|="/v1' || true)
if [[ "$root_link_leaks" != "0" ]]; then
  echo "FAIL root_link_leaks=$root_link_leaks" >&2
  grep -Eo '(href|action|src)="/[^"]+' "$TMP/portal.html" | grep -vE '="/nv-api|="/v1' | sed -n '1,20p' >&2 || true
  exit 1
fi
echo "OK root_link_leaks 0"

leak_hits=$(grep -Eio 'Sub2API|127\.0\.0\.1:1908[0-9]|10\.0\.1\.66|SMTP|DASHSCOPE|Bearer' "$TMP/portal.html" | sort -u | tr '\n' ',' || true)
if [[ -n "$leak_hits" ]]; then
  echo "FAIL upstream_leaks=$leak_hits" >&2
  exit 1
fi
echo "OK upstream_leaks none"

echo "SMOKE_OK ${BASE}"

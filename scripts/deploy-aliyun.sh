#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
install -d /opt/xapi-portal /srv/dh-nav /srv/hermes-portal
install -m 0644 services/xapi-portal/xapi_portal.py /opt/xapi-portal/xapi_portal.py
if [ -f services/xapi-v1-wrapper/xapi_v1_wrapper.py ]; then
  install -d /opt/xapi-v1-wrapper
  install -m 0755 services/xapi-v1-wrapper/xapi_v1_wrapper.py /opt/xapi-v1-wrapper/xapi_v1_wrapper.py
  if [ -f services/xapi-v1-wrapper/gateway_core.py ]; then
    install -m 0644 services/xapi-v1-wrapper/gateway_core.py /opt/xapi-v1-wrapper/gateway_core.py
  fi
  for helper in provider_adapter.py usage_wallet.py; do
    if [ -f "services/xapi-v1-wrapper/$helper" ]; then
      install -m 0644 "services/xapi-v1-wrapper/$helper" "/opt/xapi-v1-wrapper/$helper"
    fi
  done
  python3 -m py_compile /opt/xapi-v1-wrapper/xapi_v1_wrapper.py
fi
if [ -f systemd/xapi-v1-wrapper.service ]; then
  install -m 0644 systemd/xapi-v1-wrapper.service /etc/systemd/system/xapi-v1-wrapper.service
  systemctl daemon-reload
fi
if [ -f services/xapi-portal/sync_model_prices.py ]; then
  install -m 0644 services/xapi-portal/sync_model_prices.py /opt/xapi-portal/sync_model_prices.py
fi
install -m 0644 services/dh-nav/index.html /srv/dh-nav/index.html
if [ -d services/hermes-portal ]; then
  install -m 0644 services/hermes-portal/* /srv/hermes-portal/
fi
python3 -m py_compile /opt/xapi-portal/xapi_portal.py
if [ -f systemd/Caddyfile.current ]; then
  install -m 0644 systemd/Caddyfile.current /etc/caddy/Caddyfile
  caddy validate --config /etc/caddy/Caddyfile
fi
systemctl restart xapi-portal
if systemctl list-unit-files | grep -q '^xapi-v1-wrapper\.service'; then
  systemctl restart xapi-v1-wrapper
  systemctl is-active --quiet xapi-v1-wrapper
fi
systemctl is-active --quiet xapi-portal
systemctl reload caddy || systemctl restart caddy || true

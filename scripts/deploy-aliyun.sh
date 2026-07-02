#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
install -d /opt/xapi-portal
install -m 0644 services/xapi-portal/xapi_portal.py /opt/xapi-portal/xapi_portal.py
if [ -f services/xapi-portal/sync_model_prices.py ]; then
  install -m 0644 services/xapi-portal/sync_model_prices.py /opt/xapi-portal/sync_model_prices.py
fi
python3 -m py_compile /opt/xapi-portal/xapi_portal.py
systemctl restart xapi-portal
systemctl is-active --quiet xapi-portal
systemctl reload caddy || systemctl restart caddy || true
